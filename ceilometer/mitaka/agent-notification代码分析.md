#Ceilometer-agent-notification代码流程分析
[TOC]
代码/ceilometer/cmd/agent-notification.py中main()函数实现了ceilometer-agent-notification服务的初始化和启动操作。
```python
    def main():
        service.prepare_service()
        os_service.launch(CONF, notification.NotificationService(),
        				  # workers默认值为1
                          workers=CONF.notification.workers).wait()
```

##一.service启动前准备工作
1.配置log相关的参数
2.启动GMR框架
https://wiki.openstack.org/wiki/GuruMeditationReport
3.messaging，设置exchange为“ceilometer”
```python
    def prepare_service(argv=None, config_files=None):
        oslo_i18n.enable_lazy()
        log.register_options(cfg.CONF)
        log_levels = (cfg.CONF.default_log_levels +
                      ['stevedore=INFO', 'keystoneclient=INFO',
                       'neutronclient=INFO'])
        log.set_defaults(default_log_levels=log_levels)
        defaults.set_cors_middleware_defaults()

        if argv is None:
            argv = sys.argv
        cfg.CONF(argv[1:], project='ceilometer', validate_default_values=True,
                 version=version.version_info.version_string(),
                 default_config_files=config_files)

        keystone_client.setup_keystoneauth(cfg.CONF)

        log.setup(cfg.CONF, 'ceilometer')
        # NOTE(liusheng): guru cannot run with service under apache daemon, so when
        # ceilometer-api running with mod_wsgi, the argv is [], we don't start
        # guru.
        if argv:
            gmr.TextGuruMeditation.setup_autorun(version)
        messaging.setup()
```
##二.service初始化及启动
根据worker确定服务是多进程还是单进程运行
```python
    def launch(conf, service, workers=1):
        """Launch a service with a given number of workers.

        :param conf: an instance of ConfigOpts
        :param service: a service to launch, must be an instance of
               :class:`oslo_service.service.ServiceBase`
        :param workers: a number of processes in which a service will be running
        :returns: instance of a launcher that was used to launch the service
        """

        if workers is not None and workers <= 0:
            raise ValueError("Number of workers should be positive!")

        if workers is None or workers == 1:
        	#单进程初始化
            launcher = ServiceLauncher(conf)
            launcher.launch_service(service)
        else:
        	#多进程初始化
            launcher = ProcessLauncher(conf)
            launcher.launch_service(service, workers=workers)

        return launcher
```
1.单进程初始化及启动：
```python
    class ServiceLauncher(Launcher):
        """Runs one or more service in a parent process."""
        def __init__(self, conf):
            """Constructor.

            :param conf: an instance of ConfigOpts
            """
            super(ServiceLauncher, self).__init__(conf)
            self.signal_handler = SignalHandler()
```
调用父类lancher的Lanch_service方法启动服务进程：
```python
    class Launcher(object):
        """Launch one or more services and wait for them to complete."""

        def __init__(self, conf):
            """Initialize the service launcher.

            :returns: None

            """
            self.conf = conf
            conf.register_opts(_options.service_opts)
            self.services = Services()
            self.backdoor_port = (
                eventlet_backdoor.initialize_if_enabled(self.conf))

        def launch_service(self, service):
            """Load and start the given service.

            :param service: The service you would like to start, must be an
                            instance of :class:`oslo_service.service.ServiceBase`
            :returns: None

            """
            _check_service_base(service)
            service.backdoor_port = self.backdoor_port
            self.services.add(service)
```
在Service类中建立线程池，并通过回调函数self.tg.add_thread(self.run_service, service, self.done)来启动service。
```python
    class Services(object):

        def __init__(self):
            self.services = []
            self.tg = threadgroup.ThreadGroup()
            self.done = event.Event()

        def add(self, service):
            """Add a service to a list and create a thread to run it.

            :param service: service to run
            """
            self.services.append(service)
            self.tg.add_thread(self.run_service, service, self.done)
		……
        @staticmethod
        def run_service(service, done):
            """Service start wrapper.

            :param service: service to run
            :param done: event to wait on until a shutdown is triggered
            :returns: None

            """
            try:
                service.start()
            except Exception:
                LOG.exception(_LE('Error starting thread.'))
                raise SystemExit(1)
            else:
                done.wait()
```
2.多进程初始化及启动：
```python
class ProcessLauncher()
	……
    def launch_service(self, service, workers=1):
        """Launch a service with a given number of workers.

       :param service: a service to launch, must be an instance of
              :class:`oslo_service.service.ServiceBase`
       :param workers: a number of processes in which a service
              will be running
        """
        _check_service_base(service)
        wrap = ServiceWrapper(service, workers)

        LOG.info(_LI('Starting %d workers'), wrap.workers)
        #判断当前启动的worker数目，如果小于配置值，就继续初始化并启动子进程
        while self.running and len(wrap.children) < wrap.workers:
            self._start_child(wrap)
```
子进程初始化并启动过程如下：
```python
    def _child_process(self, service):
        self._child_process_handle_signal()

        # Reopen the eventlet hub to make sure we don't share an epoll
        # fd with parent and/or siblings, which would be bad
        eventlet.hubs.use_hub()

        # Close write to ensure only parent has it open
        os.close(self.writepipe)
        # Create greenthread to watch for parent to close pipe
        eventlet.spawn_n(self._pipe_watcher)

        # Reseed random number generator
        random.seed()

        launcher = Launcher(self.conf)
        launcher.launch_service(service)
        return launcher

    def _start_child(self, wrap):
        if len(wrap.forktimes) > wrap.workers:
            # Limit ourselves to one process a second (over the period of
            # number of workers * 1 second). This will allow workers to
            # start up quickly but ensure we don't fork off children that
            # die instantly too quickly.
            if time.time() - wrap.forktimes[0] < wrap.workers:
                LOG.info(_LI('Forking too fast, sleeping'))
                time.sleep(1)

            wrap.forktimes.pop(0)

        wrap.forktimes.append(time.time())

        pid = os.fork()
        if pid == 0:
            self.launcher = self._child_process(wrap.service)
            while True:
                self._child_process_handle_signal()
                status, signo = self._child_wait_for_exit_or_signal(
                    self.launcher)
                if not _is_sighup_and_daemon(signo):
                    self.launcher.wait()
                    break
                self.launcher.restart()

            os._exit(status)

        LOG.debug('Started child %d', pid)

        wrap.children.add(pid)
        self.children[pid] = wrap

        return pid
```
在子进程启动过程中，主要解决与父进程之间的同步与通信的问题，然后子进程通过Launcher类来启动service（这一点与单进程启动service一致）。

##三.ceilometer-agent-notification服务启动及运行

通过NotificationService().start()方法完成ceilometer-agent-notification服务的启动操作。
启动过程实现了以下任务

###1.根据pipeline.yaml装配pipelines
---
pipeline.yaml中分为source和sink两大部分。
sources定义了pipeline的构建方式。
sinks定义了sample在pipeline中的转换方法和发布方式。

pipeline.yaml
```python
    sources:
        - name: meter_source
          interval: 600
          meters:
              - "*"
          sinks:
              - meter_sink
        - name: cpu_source
          interval: 600
          meters:
              - "cpu"
          sinks:
              - cpu_sink
              - cpu_delta_sink
        ……
    sinks:
        - name: meter_sink
          transformers:
          publishers:
              - notifier://
        - name: cpu_sink
          transformers:
              - name: "rate_of_change"
                parameters:
                    target:
                        name: "cpu_util"
                        unit: "%"
                        type: "gauge"
                        scale: "100.0 / (10**9 * (resource_metadata.cpu_number or 1))"
          publishers:
              - notifier://
        - name: cpu_delta_sink
          transformers:
              - name: "delta"
                parameters:
                    target:
                        name: "cpu.delta"
                    growth_only: True
          publishers:
              - notifier://
        ……
```
\ceilometer\notification.py
NotificationService().start()中通过以下调用初始化pipeline。
```python
    self.pipeline_manager = pipeline.setup_pipeline()
```
\ceilometer\pipeline.py
```python
    def setup_pipeline(transformer_manager=None):
    """Setup pipeline manager according to yaml config file."""
    	cfg_file = cfg.CONF.pipeline_cfg_file
    	return _setup_pipeline_manager(cfg_file, transformer_manager)

    def _setup_pipeline_manager(cfg_file, transformer_manager, p_type=SAMPLE_TYPE):
        if not os.path.exists(cfg_file):
            cfg_file = cfg.CONF.find_file(cfg_file)

        LOG.debug("Pipeline config file: %s", cfg_file)
		//从配置文件中读取配置信息
        with open(cfg_file) as fap:
            data = fap.read()

        pipeline_cfg = yaml.safe_load(data)
        LOG.info(_LI("Pipeline config: %s"), pipeline_cfg)
		//根据配置进行pm初始化
        return PipelineManager(pipeline_cfg,
                               transformer_manager or
                               extension.ExtensionManager(
                                   'ceilometer.transformer',
                               ), p_type)
```
PipelineManager定义如下
```python
    class PipelineManager(object):
    """Pipeline Manager
        ……
        def __init__(self, cfg, transformer_manager, p_type=SAMPLE_TYPE):
            """Setup the pipelines according to config.
            ……
            self.pipelines = []
            if not ('sources' in cfg and 'sinks' in cfg):
                raise PipelineException("Both sources & sinks are required",
                                        cfg)
            LOG.info(_LI('detected decoupled pipeline config format'))

            unique_names = set()
            sources = []
            for s in cfg.get('sources', []):
                name = s.get('name')
                if name in unique_names:
                    raise PipelineException("Duplicated source names: %s" %
                                            name, self)
                else:
                    unique_names.add(name)
                    sources.append(p_type['source'](s))  //source实例化
            unique_names.clear()

            sinks = {}
            for s in cfg.get('sinks', []):
                name = s.get('name')
                if name in unique_names:
                    raise PipelineException("Duplicated sink names: %s" %
                                            name, self)
                else:
                    unique_names.add(name)
                    sinks[s['name']] = p_type['sink'](s, transformer_manager) //sink实例化
            unique_names.clear()

            for source in sources:
                source.check_sinks(sinks)
                for target in source.sinks:
                    pipe = p_type['pipeline'](source, sinks[target]) //将source和sink装配成pipeline
                    if pipe.name in unique_names:
                        raise PipelineException(
                            "Duplicate pipeline name: %s. Ensure pipeline"
                            " names are unique. (name is the source and sink"
                            " names combined)" % pipe.name, cfg)
                    else:
                        unique_names.add(pipe.name)
                        self.pipelines.append(pipe)
            unique_names.clear()
```
###2.监听
NotificationService().start()通过调用_configure_main_queue_listeners方法，完成监听并处理notifications的初始化。
```python```python
	self._configure_main_queue_listeners(self.pipe_manager,
                                             self.event_pipe_manager)
```
_configure_main_queue_listeners()实现的功能：
####1)加载命名空间'ceilometer.notification'中插件.
   在NotificationService().nfigure_main_queue_listeners()函数中通过以下调用加载命名空间'ceilometer.notification'中插件：
```python
	notification_manager = self._get_notifications_manager(pipe_manager)
```
_get_notifications_manager()定义如下：
```python
    def _get_notifications_manager(cls, pm):
        return extension.ExtensionManager(
            namespace=cls.NOTIFICATION_NAMESPACE,
            invoke_on_load=True,
            invoke_args=(pm, )
        )
```
上面实现了从entry_points中加载ceilometer.notification命名空间中的插件。
```python
    [entry_points]
    ceilometer.notification =
        instance = ceilometer.compute.notifications.instance:Instance
        instance_scheduled = ceilometer.compute.notifications.instance:InstanceScheduled
        network = ceilometer.network.notifications:Network
        subnet = ceilometer.network.notifications:Subnet
        port = ceilometer.network.notifications:Port
        ……
```
####2)连接到消息总线来监听oslo-messaging消息框架中nova/glance /cinder等服务的消息。
```python
        endpoints = []
        if cfg.CONF.notification.store_events:
            endpoints.append(
                event_endpoint.EventsNotificationEndpoint(event_pipe_manager))

        targets = []
        for ext in notification_manager:
            handler = ext.obj
            if (cfg.CONF.notification.disable_non_metric_meters and
                    isinstance(handler, base.NonMetricNotificationBase)):
                continue
            LOG.debug('Event types from %(name)s: %(type)s'
                      ' (ack_on_error=%(error)s)',
                      {'name': ext.name,
                       'type': ', '.join(handler.event_types),
                       'error': ack_on_error})
            # NOTE(gordc): this could be a set check but oslo_messaging issue
            # https://bugs.launchpad.net/oslo.messaging/+bug/1398511
            # This ensures we don't create multiple duplicate consumers.
            for new_tar in handler.get_targets(cfg.CONF):
                if new_tar not in targets:
                    targets.append(new_tar)
            endpoints.append(handler)

		#target可以理解为要监听的消息
        #endpoint可以理解为监听到消息后的处理入口
        
        urls = cfg.CONF.notification.messaging_urls or [None]
        for url in urls:
            transport = messaging.get_transport(url)
            listener = messaging.get_batch_notification_listener(
                transport, targets, endpoints,
                batch_size=cfg.CONF.notification.batch_size,
                batch_timeout=cfg.CONF.notification.batch_timeout)
            listener.start()
            self.listeners.append(listener)
```
通过messaging.get_batch_notification_listener（）回调插件中的get_targets()获得监听队列的exchange和topic，实施监听，以instance为例(topic=notifications，exchange=nova)
```python
    class ComputeNotificationBase(plugin_base.NotificationBase):
        def get_targets(self, conf):
            """Return a sequence of oslo_messaging.Target

            This sequence is defining the exchange and topics to be connected for
            this plugin.
            """
            return [oslo_messaging.Target(topic=topic,
                                          exchange=conf.nova_control_exchange)
                    for topic in self.get_notification_topics(conf)]
```
####3)消息处理。
根据不同监控项和具体插件调用不同的process_notification方法，将接收到的通知转换成采样数据的格式；
\ceilometer\agent\plugin_base.py
```python
	class NotificationBase(PluginBase):
        """Base class for plugins that support the notification API."""
		……
        def _process_notifications(self, priority, notifications):
            for notification in notifications:
                try:
                	#将notification格式化
                    notification = messaging.convert_to_old_notification_format(
                        priority, notification)
                    self.to_samples_and_publish(context.get_admin_context(),
                                                notification)
                except Exception:
                    LOG.error(_LE('Fail to process notification'), exc_info=True)

        def to_samples_and_publish(self, context, notification):
            """Return samples produced by *process_notification*.

            Samples produced for the given notification.
            :param context: Execution context from the service or RPC call
            :param notification: The notification to process.
            """
            #调用子类的process_notification函数将notification转化为sample
            #然后通过pipeline做进一步处理
            with self.manager.publisher(context) as p:
                p(list(self.process_notification(notification)))

```
NotificationBase()子类 UserMetadataAwareInstanceNotificationBase()中process_notification()方法的定义：
```python
	class UserMetadataAwareInstanceNotificationBase(
            notifications.ComputeNotificationBase):
        """Consumes notifications containing instance user metadata."""

        def process_notification(self, message):
            instance_properties = self.get_instance_properties(message)
            if isinstance(instance_properties.get('metadata'), dict):
                src_metadata = instance_properties['metadata']
                del instance_properties['metadata']
                util.add_reserved_user_metadata(src_metadata, instance_properties)
            return self.get_sample(message)
```
UserMetadataAwareInstanceNotificationBase调用子类Instance中get_sample()方法，将notifications转化成sample
```python
    class Instance(ComputeInstanceNotificationBase,
                   plugin_base.NonMetricNotificationBase):
        def get_sample(self, message):
            yield sample.Sample.from_notification(
                name='instance',
                type=sample.TYPE_GAUGE,
                unit='instance',
                volume=1,
                user_id=message['payload']['user_id'],
                project_id=message['payload']['tenant_id'],
                resource_id=message['payload']['instance_id'],
                message=message)
```
将监控项采样数据样本sample经过pipeline进行转换后，实现发布。
\ceilometer\ pipeline.py
PollingManager().publisher()
```python
    def publisher(self, context):
        """Build a new Publisher for these manager pipelines.

        :param context: The context.
        """
        return PublishContext(context, self.pipelines)
```
PublishContext()
```python
    class PublishContext(object):

        def __init__(self, context, pipelines=None):
            pipelines = pipelines or []
            self.pipelines = set(pipelines)
            self.context = context

        def add_pipelines(self, pipelines):
            self.pipelines.update(pipelines)

        def __enter__(self):
            def p(data):
                for p in self.pipelines:
                    p.publish_data(self.context, data)
            return p

        def __exit__(self, exc_type, exc_value, traceback):
            for p in self.pipelines:
                p.flush(self.context)
```
SamplePipelin().publish_data()
```python
    def publish_data(self, ctxt, samples):
        if not isinstance(samples, list):
            samples = [samples]
        supported = [s for s in samples if self.source.support_meter(s.name)
                     and self._validate_volume(s)]
        self.sink.publish_samples(ctxt, supported)
```
SampleSink().publish_samples()这里会将sample按照pipeline中transformer的规则进行转换，得到新的sample并调用publisher发布出去
```python
    def _publish_samples(self, start, ctxt, samples):
        """Push samples into pipeline for publishing.

        :param start: The first transformer that the sample will be injected.
                      This is mainly for flush() invocation that transformer
                      may emit samples.
        :param ctxt: Execution context from the manager or service.
        :param samples: Sample list.

        """

        transformed_samples = []
        if not self.transformers:
            transformed_samples = samples
        else:
            for sample in samples:
                LOG.debug(
                    "Pipeline %(pipeline)s: Transform sample "
                    "%(smp)s from %(trans)s transformer", {'pipeline': self,
                                                           'smp': sample,
                                                           'trans': start})
                sample = self._transform_sample(start, ctxt, sample)
                if sample:
                    transformed_samples.append(sample)

        if transformed_samples:
            for p in self.publishers:
                try:
                    p.publish_samples(ctxt, transformed_samples)
                except Exception:
                    LOG.exception(_(
                        "Pipeline %(pipeline)s: Continue after error "
                        "from publisher %(pub)s") % ({'pipeline': self,
                                                      'pub': p}))

    def publish_samples(self, ctxt, samples):
        self._publish_samples(0, ctxt, samples)
```
\ceilometer\publisher\ messaging.py
MessagingPublisher()
```python
    def publish_samples(self, context, samples):
        """Publish samples on RPC.

        :param context: Execution context from the service or RPC call.
        :param samples: Samples from pipeline after transformation.

        """

        meters = [
            utils.meter_message_from_counter(
                sample, cfg.CONF.publisher.telemetry_secret)
            for sample in samples
        ]
        topic = cfg.CONF.publisher_notifier.metering_topic
        self.local_queue.append((context, topic, meters))

        if self.per_meter_topic:
            for meter_name, meter_list in itertools.groupby(
                    sorted(meters, key=operator.itemgetter('counter_name')),
                    operator.itemgetter('counter_name')):
                meter_list = list(meter_list)
                topic_name = topic + '.' + meter_name
                LOG.debug('Publishing %(m)d samples on %(n)s',
                          {'m': len(meter_list), 'n': topic_name})
                self.local_queue.append((context, topic_name, meter_list))

        self.flush()
```
NotifierPublisher()
```python
    def _send(self, context, event_type, data):
        try:
            self.notifier.sample(context.to_dict(), event_type=event_type,
                                 payload=data)
        except oslo_messaging.MessageDeliveryFailure as e:
            raise_delivery_failure(e)
```