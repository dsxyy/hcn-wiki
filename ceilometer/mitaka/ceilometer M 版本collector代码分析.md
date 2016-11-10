
[TOC]


## collector daemon
ceilometer为openstack项目提供数据收集的服务。原始数据的收集方式有两种：**ceilometer polling agent**的主动轮询和各openstack核心组件的自主上报，这两种收集方式都将原始数据发送到消息队列。**ceilometer notification agent**监听该消息队列，并将这些原始数据转换成sample和event，再发布到配置的目的端。可配的发布方式包括direct、notifier、udp、kafka和file。**ceilometer collector**是可选服务，它从notification队列中消费sample和event消息，如果配置了udp方式，也获取udp发布的sample。然后将数据dispatch到需要分配的目的端：database、file、http、gnocchi，这个目的端是个多值配置。

## collector 启动流程
==collector daemon入口：==ceilometer/cmd/collector.py
service.prepare_service()是ceilometer通用的，完成 配置并启动log、启动GMR框架、设置messaging的exchange为“ceilometer”。
```python
def main():
    service.prepare_service()
    os_service.launch(CONF, collector.CollectorService(),
                      workers=CONF.collector.workers).wait()

```
==collector服务启动流程：==ceilometer/collector.py
collector服务的启动流程，在该类的start方法中。根据配置项（meter_dispatchers和event_dispatchers），加载相应meter和event的dispatcher插件；获取进程消息通信的transport；分别设置meter和event的监听topic和消息处理配置，并启动消息处理流程。同时添加udp消息处理流程。
```python
class CollectorService(os_service.Service):
    """Listener for the collector service."""
    def start(self):
        """Bind the UDP socket and handle incoming data."""
        # ensure dispatcher is configured before starting other services
        # 加载meter和event的dispatcher插件
        dispatcher_managers = dispatcher.load_dispatcher_manager()
        (self.meter_manager, self.event_manager) = dispatcher_managers
        ...
        # 添加udp处理
        if cfg.CONF.collector.udp_address:
            self.tg.add_thread(self.start_udp)
        # 获取进程消息通信的transport
        transport = messaging.get_transport(optional=True)
        if transport:
            # 设置并启动meter的dispatcher
            if list(self.meter_manager):
                # 获取meter需要监听的消息队列topic
                sample_target = oslo_messaging.Target(
                    topic=cfg.CONF.publisher_notifier.metering_topic)
                # 关联meter的消息和处理函数，处理函数映射在SampleEndpoint中完成
                self.sample_listener = (
                    messaging.get_batch_notification_listener(
                        transport, [sample_target],
                        [SampleEndpoint(self.meter_manager)],
                        allow_requeue=True,
                        batch_size=cfg.CONF.collector.batch_size,
                        batch_timeout=cfg.CONF.collector.batch_timeout))
                # 启动meter的消息处理
                self.sample_listener.start()

            # 设置并启动event的dispatcher
            if cfg.CONF.notification.store_events and list(self.event_manager):
               ...

```

==dispatcher插件加载：==
ceilometer/dispatcher/__init__.py
根据命名空间和配置项加载对应的插件，meter或者event的dispatcher配置都是多值项，返回的dispatcher是list。插件处理时，消息会分别在所配置的插件中处理。
```python
def _load_dispatcher_manager(dispatcher_type):
    # 组装命名空间
    namespace = 'ceilometer.dispatcher.%s' % dispatcher_type
    # 适配ceilometer.conf中的配置项
    conf_name = '%s_dispatchers' % dispatcher_type

    LOG.debug('loading dispatchers from %s', namespace)
    # set propagate_map_exceptions to True to enable stevedore
    # to propagate exceptions.
    # 通过stevedore，以命名空间和插件名，加载插件。插件名是conf中配置的dispatcher方式
    dispatcher_manager = named.NamedExtensionManager(
        namespace=namespace,
        names=getattr(cfg.CONF, conf_name),
        invoke_on_load=True,
        invoke_args=[cfg.CONF],
        propagate_map_exceptions=True)
    if not list(dispatcher_manager):
        LOG.warning(_LW('Failed to load any dispatchers for %s'),
                    namespace)
    return dispatcher_manager

```

==插件处理函数的关联：==
加载插件后还需要关联消息处理的函数，通过代码可以看到，对每一种插件，sample是调用record_metering_data函数处理，event是调用record_events进行处理的。
```python
class CollectorEndpoint(object):
    def __init__(self, dispatcher_manager):
        self.dispatcher_manager = dispatcher_manager

    def sample(self, messages):
        """RPC endpoint for notification messages

        When another service sends a notification over the message
        bus, this method receives it.
        """
        # 从消息中获取消息体
        samples = list(chain.from_iterable(m["payload"] for m in messages))
        try:
            # 映射消息体和消息处理函数
            self.dispatcher_manager.map_method(self.method, samples)
        except Exception:
            LOG.exception(_LE("Dispatcher failed to handle the %s, "
                              "requeue it."), self.ep_type)
            return oslo_messaging.NotificationResult.REQUEUE


class SampleEndpoint(CollectorEndpoint):
    # meter的消息处理函数
    method = 'record_metering_data'
    ep_type = 'sample'


class EventEndpoint(CollectorEndpoint):
    # event的消息处理函数
    method = 'record_events'
    ep_type = 'event'

```

## collector的http分配方式
设置collector的meter和event都使用http分配方式，需要在配置文件ceilometer.conf中设置
```
[DEFAULT]
meter_dispatchers = http
event_dispatchers = http
```
- 这两个是多值配置项，如果想要设置为多种分配方式，设置例子为：
```
[DEFAULT]
meter_dispatchers = http
meter_dispatchers = database
```

设置http服务器
```
[dispatcher_http]
target = http://127.0.0.1:8080
这个配置项是meter和event共用的
```

```python
class HttpDispatcher(dispatcher.MeterDispatcherBase,
                     dispatcher.EventDispatcherBase):
    """Dispatcher class for posting metering/event data into a http target.

    To enable this dispatcher, the following option needs to be present in
    ceilometer.conf file::

        [DEFAULT]
        meter_dispatchers = http
        event_dispatchers = http

    Dispatcher specific options can be added as follows::

        [dispatcher_http]
        target = www.example.com
        event_target = www.example.com
        timeout = 2
    """

    def __init__(self, conf):
        super(HttpDispatcher, self).__init__(conf)
        self.headers = {'Content-type': 'application/json'}
        self.timeout = self.conf.dispatcher_http.timeout
        self.target = self.conf.dispatcher_http.target
        self.event_target = (self.conf.dispatcher_http.event_target or
                             self.target)

    def record_metering_data(self, data):
        ...

        for meter in data:
            ...
                try:
                    # Every meter should be posted to the target
                    # post meter数据到配置的target
                    res = requests.post(self.target,
                                        data=json.dumps(meter),
                                        headers=self.headers,
                                        timeout=self.timeout)
                    LOG.debug('Message posting finished with status code '
                              '%d.', res.status_code)
                except Exception as err:
                    LOG.exception(_('Failed to record metering data: %s'),
                                  err)
            else:
                LOG.warning(_(
                    'message signature invalid, discarding message: %r'),
                    meter)

    def record_events(self, events):
        ...

```
