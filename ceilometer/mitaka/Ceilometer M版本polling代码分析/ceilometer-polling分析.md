
[TOC]


#ceilometer polling agents

ceilometer数据采集由ceilometer polling agents 和 ceilometer notification agents完成；ceilometer polling agents是由ceilometer发起主动轮询所关心的数据；ceilometer notification agents则是由各个模块上报数据到notificaton队列，然后再由ceilometer notification agents抓取进行处理；经过ceilometer polling agents和ceilometer notification agents处理后的数据最后会发送到notification队列，由ceilometer collector收集写入数据库或做其它处理。

## 概述

Ceilometer polling分为compute、central和ipmi三部分，分别对应不同的服务，使用同一套代码；在启动服务时，传入不同的参数(compute/central/ipmi)，以此来加载对应的entry_points，实现轮询不同的pollster数据。
tecs3.0(Openstack Mitaka)版本ceilometer总体架构：

![overall.JPG](.\overall.JPG)

ceilometer收集数据示意图：
![collect-data.JPG](.\collect-data.JPG)

ceilometer提供两种方式收集数据：
- Bus listener agent 从notifications队列取消息转换为ceilometer samples

![notification.JPG](.\notification.JPG)

ceilometer-notification agent监听notification队列，除了ceilometer内部通信，nova/glance/neutron/cinder/swift/keystone/heat都向该队列发送数据
notification守护进程使用ceilometer.notification加载一个或多个listener插件。每一个插件可以监听任意topics，但默认监听notificaton.info。监听插件根据指定的topics抓取数据，并把它们重新发布到合适的插件(endpoints)以处理成events和samples

- polling agents 以固定时间间隔通过轮询其它模块API或其它工具收集数据

![polling.JPG](.\polling.JPG)

polling agent可以配置为轮询本地hypervisor或者APIs
计算资源的轮询是由polling compute agent处理的，它在计算节点执行(访问hypervisor更有效)
polling 通过服务API轮询非计算资源的处理是由运行在控制节点的polling central agent完成的

## ceilometer-polling启动流程
通过启动service时传入的参数确认启动'compute', 'central', 'ipmi'中的一个
pollster-list用于确认加载哪些entry_points；如果为[]，则加载所有的entry_points，否则加载pollster-list对应的entry_points

ceilometer\ceilometer\cmd\polling.py
```python
CLI_OPTS = [
    MultiChoicesOpt('polling-namespaces',
                    default=['compute', 'central'],
                    choices=['compute', 'central', 'ipmi'],
                    dest='polling_namespaces',
                    help='Polling namespace(s) to be used while '
                         'resource polling'),
    MultiChoicesOpt('pollster-list',
                    default=[],
                    dest='pollster_list',
                    help='List of pollsters (or wildcard templates) to be '
                         'used while polling'),
]
def main():
    service.prepare_service()
    os_service.launch(CONF, manager.AgentManager(CONF.polling_namespaces,
                                                 CONF.pollster_list)).wait()
```

初始化操作主要实现了以下内容的操作：

- 先根据指定参数（compute/central/ipmi）获取命名空间ceilometer.poll.compute|central|ipmi，然后获取与ceilometer.poll.compute|central|ipmi相匹配的所有插件，并加载；ceilometer.poll.compute|central|ipmi所指定的插件描述了如何获取采样数据；
- 获取命名空间**ceilometer.discover**，获取与`ceilometer.discover`相匹配的所有插件，并加载；`ceilometer.discover`所指定的插件描述了如何发现主机上的所监控的资源

ceilometer\ceilometer\agent\manager.py
```python
class AgentManager(service_base.BaseService):
     def __init__(self, namespaces=None, pollster_list=None):
         namespaces = namespaces or ['compute', 'central']
         pollster_list = pollster_list or []
         group_prefix = cfg.CONF.polling.partitioning_group_prefix
 
         # features of using coordination and pollster-list are exclusive, and
         # cannot be used at one moment to avoid both samples duplication and
         # samples being lost
         if pollster_list and cfg.CONF.coordination.backend_url:
             raise PollsterListForbidden()
 
         super(AgentManager, self).__init__()
 
         def _match(pollster):
             """Find out if pollster name matches to one of the list."""
             return any(utils.match(pollster.name, pattern) for
                        pattern in pollster_list)
 
         if type(namespaces) is not list:
             namespaces = [namespaces]
 
         # we'll have default ['compute', 'central'] here if no namespaces will
         # be passed
         #加载entry_points.txt中namespace对应插件
         extensions = (self._extensions('poll', namespace).extensions
                       for namespace in namespaces)
         # get the extensions from pollster builder
         extensions_fb = (self._extensions_from_builder('poll', namespace)
                          for namespace in namespaces)
         if pollster_list:
             extensions = (moves.filter(_match, exts)
                           for exts in extensions)
             extensions_fb = (moves.filter(_match, exts)
                              for exts in extensions_fb)
 
         self.extensions = list(itertools.chain(*list(extensions))) + list(
             itertools.chain(*list(extensions_fb)))
 
         self.discovery_manager = self._extensions('discover')
         self.context = context.RequestContext('admin', 'admin', is_admin=True)
         self.partition_coordinator = coordination.PartitionCoordinator()
 
         # Compose coordination group prefix.
         # We'll use namespaces as the basement for this partitioning.
         namespace_prefix = '-'.join(sorted(namespaces))
         self.group_prefix = ('%s-%s' % (namespace_prefix, group_prefix)
                              if group_prefix else namespace_prefix)
         #获取polling agents处理后要发送数据的消息队列
         self.notifier = oslo_messaging.Notifier(
             messaging.get_transport(),
             driver=cfg.CONF.publisher_notifier.telemetry_driver,
             publisher_id="ceilometer.polling")
 
         self._keystone = None
         self._keystone_last_exception = None
```

服务启动流程代码：

oslo_service\service.py
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
        launcher = ServiceLauncher(conf)
        launcher.launch_service(service)
    else:
        launcher = ProcessLauncher(conf)
        launcher.launch_service(service, workers=workers)

    return launcher
```

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

```python
class ServiceLauncher(Launcher):
    """Runs one or more service in a parent process."""
    def wait(self):
        """Wait for a service to terminate and restart it on SIGHUP.

        :returns: termination status
        """
        systemd.notify_once()
        self.signal_handler.clear()
        while True:
            self.handle_signal()
            status, signo = self._wait_for_exit_or_signal()
            if not _is_sighup_and_daemon(signo):
                break
            self.restart()

        super(ServiceLauncher, self).wait()
        return status
```

```python
class Launcher(object):

    def restart(self):
        """Reload config files and restart service.

        :returns: None

        """
        self.conf.reload_config_files()
        self.services.restart()
```

```python
class Services(object):

    def restart(self):
        """Reset services and start them in new threads."""
        self.stop()
        self.done = event.Event()
        for restart_service in self.services:
            restart_service.reset()
            self.tg.add_thread(self.run_service, restart_service, self.done)

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

如下代码所做的处理：
- 读取配置文件pipeline.yaml，获取所有的sources配置
- 以每个meter项的interval为key创建定时任务列表，并其添加到对应采集周期的定时任务列表中

ceilometer\ceilometer\agent\manager.py
```python
    def start(self):
        #加载pipeline.yaml文件，读取source信息
        self.polling_manager = pipeline.setup_polling()

        self.partition_coordinator.start()
        self.join_partitioning_groups()

        #根据每个meter的interval创建PollingTask
        self.pollster_timers = self.configure_polling_tasks()

        self.init_pipeline_refresh()
```

注意：因pipeline.yaml里的meter_source项的默认配置是"\*"，故entry_points.txt里定义的所有采集指标都会有对应一个采集并上报原始数据任务并加入600s的任务列表里。如果不想上报原始数据，则配置项应改为：`"!*"`

/etc/ceilometer/pipeline.yaml：
```
sources:
    - name: meter_source
      interval: 600
      meters:
          - "*"
      sinks:
          - meter_sink
```

## ceilometer-polling模块定时轮询流程

加载pipeline.yaml配置，通过interval分类创建timer，相同interval的pollster会同时触发。

ceilometer\ceilometer\agent\manager.py
```python
class AgentManager(service_base.BaseService):
    def create_polling_task(self):
        """Create an initially empty polling task."""
        return PollingTask(self)
    def setup_polling_tasks(self):
        polling_tasks = {}
        for source in self.polling_manager.sources:
            polling_task = None
            for pollster in self.extensions:
                if source.support_meter(pollster.name):
                    polling_task = polling_tasks.get(source.get_interval())
                    if not polling_task:
                        polling_task = self.create_polling_task()
                        polling_tasks[source.get_interval()] = polling_task
                    #加入轮询数据调用的方法（函数），格式见下段entry_points.txt内容
                    polling_task.add(pollster, source)
        return polling_tasks
    def configure_polling_tasks(self):
        # allow time for coordination if necessary
        delay_start = self.partition_coordinator.is_active()

        # set shuffle time before polling task if necessary
        delay_polling_time = random.randint(
            0, cfg.CONF.shuffle_time_before_polling_task)

        pollster_timers = []
        data = self.setup_polling_tasks()
        for interval, polling_task in data.items():
            delay_time = (interval + delay_polling_time if delay_start
                          else delay_polling_time)
            pollster_timers.append(self.tg.add_timer(interval,
                                   self.interval_task,
                                   initial_delay=delay_time,
                                   task=polling_task))
        self.tg.add_timer(cfg.CONF.coordination.heartbeat,
                          self.partition_coordinator.heartbeat)

        return pollster_timers
    def interval_task(self, task):
        # NOTE(sileht): remove the previous keystone client
        # and exception to get a new one in this polling cycle.
        self._keystone = None
        self._keystone_last_exception = None
        #开始轮询数据
        task.poll_and_notify()

```

entry_points.txt
```
[ceilometer.poll.central] 
rgw.usage = ceilometer.objectstore.rgw:UsagePollster
network.services.vpn.connections = ceilometer.network.services.vpnaas:IPSecConnectionsPollster
rgw.containers.objects = ceilometer.objectstore.rgw:ContainersObjectsPollster
image = ceilometer.image.glance:ImagePollster
...
[ceilometer.poll.compute] 
disk.write.requests.rate = ceilometer.compute.pollsters.disk:WriteRequestsRatePollster
disk.device.allocation = ceilometer.compute.pollsters.disk:PerDeviceAllocationPollster
disk.latency = ceilometer.compute.pollsters.disk:DiskLatencyPollster
... 
[ceilometer.poll.ipmi] 
hardware.ipmi.voltage = ceilometer.ipmi.pollsters.sensor:VoltageSensorPollster
hardware.ipmi.node.power = ceilometer.ipmi.pollsters.node:PowerPollster
hardware.ipmi.node.cups = ceilometer.ipmi.pollsters.node:CUPSIndexPollster
...
```

```python
class PollingTask(object):
    def poll_and_notify(self):
        """Polling sample and notify."""
        cache = {}
        discovery_cache = {}
        poll_history = {}
        for source_name in self.pollster_matches:
            for pollster in self.pollster_matches[source_name]:
                key = Resources.key(source_name, pollster)
                candidate_res = list(
                    self.resources[key].get(discovery_cache))
                if not candidate_res and pollster.obj.default_discovery:
                    #pollster.obj.default_discovery值为local_instances
                    candidate_res = self.manager.discover(
                        [pollster.obj.default_discovery], discovery_cache)

                # Remove duplicated resources and black resources. Using
                # set() requires well defined __hash__ for each resource.
                # Since __eq__ is defined, 'not in' is safe here.
                polling_resources = []
                black_res = self.resources[key].blacklist
                history = poll_history.get(pollster.name, [])
                for x in candidate_res:
                    if x not in history:
                        history.append(x)
                        if x not in black_res:
                            polling_resources.append(x)
                poll_history[pollster.name] = history

                # If no resources, skip for this pollster
                if not polling_resources:
                    p_context = 'new ' if history else ''
                    LOG.info(_LI("Skip pollster %(name)s, no %(p_context)s"
                                 "resources found this cycle"),
                             {'name': pollster.name, 'p_context': p_context})
                    continue

                LOG.info(_LI("Polling pollster %(poll)s in the context of "
                             "%(src)s"),
                         dict(poll=pollster.name, src=source_name))
                try:
                    #轮询获取meter数据
                    samples = pollster.obj.get_samples(
                        manager=self.manager,
                        cache=cache,
                        resources=polling_resources
                    )
                    sample_batch = []

                    for sample in samples:
                        sample_dict = (
                            publisher_utils.meter_message_from_counter(
                                sample, self._telemetry_secret
                            ))
                        #将samples送到notification消息队列，由notification agents做转换后再发布
                        if self._batch:
                            sample_batch.append(sample_dict)
                        else:
                            self._send_notification([sample_dict])

                    if sample_batch:
                        self._send_notification(sample_batch)

                except plugin_base.PollsterPermanentError as err:
                    LOG.error(_(
                        'Prevent pollster %(name)s for '
                        'polling source %(source)s anymore!')
                        % ({'name': pollster.name, 'source': source_name}))
                    self.resources[key].blacklist.extend(err.fail_res_list)
                except Exception as err:
                    LOG.warning(_(
                        'Continue after error from %(name)s: %(error)s')
                        % ({'name': pollster.name, 'error': err}),
                        exc_info=True)
```

举例：下面的代码的功能是获取对应虚机的cpu使用时间
ceilometer\ceilometer\compute\pollsters\cpu.py
```python
class CPUPollster(pollsters.BaseComputePollster):

    def get_samples(self, manager, cache, resources):
        for instance in resources:
            LOG.debug('checking instance %s', instance.id)
            try:
                #调用libvirt接口获取cpu使用时间
                cpu_info = self.inspector.inspect_cpus(instance)
                LOG.debug("CPUTIME USAGE: %(instance)s %(time)d",
                          {'instance': instance,
                           'time': cpu_info.time})
                cpu_num = {'cpu_number': cpu_info.number}
                #生成sample并返回
                yield util.make_sample_from_instance(
                    instance,
                    name='cpu',
                    type=sample.TYPE_CUMULATIVE,
                    unit='ns',
                    volume=cpu_info.time,
                    additional_metadata=cpu_num,
                )
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except virt_inspector.InstanceShutOffException as e:
                LOG.debug('Instance %(instance_id)s was shut off while '
                          'getting samples of %(pollster)s: %(exc)s',
                          {'instance_id': instance.id,
                           'pollster': self.__class__.__name__, 'exc': e})
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('Obtaining CPU time is not implemented for %s',
                          self.inspector.__class__.__name__)
            except Exception as err:
                LOG.exception(_('could not get CPU time for %(id)s: %(e)s'),
                              {'id': instance.id, 'e': err})
```

# 参考资料
https://github.com/openstack/ceilometer/tree/stable/mitaka
http://docs.openstack.org/developer/ceilometer/architecture.html?highlight=aodh