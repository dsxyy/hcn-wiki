### [HCN-20160509-003]分析TECS 20 Ceilometer功能反合M版本
#### 611004157663【HCN】ZXTECS1.0中ceilometer相关功能反合ZXTECS2.0
   ceilometer指标项裁剪
苏正伟处理：
        611004113596【ZXOPENCOS】从云盘启动虚拟机，disk.total.size这个指标上报数据有误 
        611004098690 [ZXOPENCOS]新增虚拟机vcpu/memory/disk.total.size指标poll查询方法
        611004066551		[ceilometer] 增加统计虚拟机磁盘信息	
        611004061585		[ceilometer] 增加数据库定时清理功能	
        EC614005245714 请tecs平台配合查看ceilometer数据达到8万条的原因
#### 611004157663【HCN】ZXTECS1.0中ceilometer相关功能反合ZXTECS2.0
614005113316【HCN】celometer采集项compute.node.disk.read/write.bytes.rate上报时间修改为600s
代码优化：611004157663【HCN】ZXTECS1.0中ceilometer相关功能反合ZXTECS2.0
补齐单元测试：611004157663【HCN】ZXTECS1.0中ceilometer相关功能反合ZXTECS2.0
611004169292【HCN】物理机带宽上报功能，打印日志优化
已处理：611004118306【HCN】上报物理机网卡带宽功能
        611004066557[ceilometer] 增加物理机网口速率统计
        611004066554[ceilometer] 增加物理机磁盘信息统计
        611004089961 磁盘多路径统计信息过滤
        611004083485【ZXOPENCOS】物理节点网卡监控信息不应该重复统计bond和bond的成员口
        611004086035 【ZXOPENCOS】物理网口监控指标中监控了macvtap类型的虚拟口
        611004079198 ceilometer物理机磁盘和网络读取速率需要增加metadata信息
        611004077609 ceilometer物理机检测项名称修改
        611004076236【ZXOPENCOS】换了p3b1版本,ceilometer-agen cpu占用率挺高 zhoubin172495
        611004074575[unittest] ceilometer新增功能单元测试补齐	zhoubin10072495
#### 611004208080 【TECS】TECS2.0 P4B1版本，disk.total.size没有统计挂载的云硬盘
#### #23236Ceilometer物理机指标上报不依赖是否创建虚机
#### 611004209724【TECS2.0 NFV网关商用系统测试】ceilometer的统计项和1.0中的不一致，导致vdirector统计不到数据。
#### 2015.12.08 -- 2015.12.14 没查到相关log记录
 http://gerrit.zte.com.cn/gitweb?p=tecs/ceilometer.git;a=log;h=refs/heads/dev
#### 611004217205【TECS】虚拟机disk.total.size指标上报异常
  flavor配置光驱的时候，使用这个flavor启动虚拟机，disk.total.size指标上报异常，正常的虚拟机也无法上报
#### #26986 Ceilometer-api连接失败
614005181765【TECS】lb双机环境，api-monitor不能正常工作
#### 30157 ceilometer支持SR-IOV网卡性能统计
[EC614005227320]【TECS】使用SRIOV direct网卡的虚拟机统计数据失败
#### 614005205525:if cpu_util volume greater than 100, then set it to 100
#### Refs #33739: ceilometer receives cinder total/free/allocated/provisioned/virtual_free notifications

#### 614005195093 由于容器内Director与OpenStack使用的数据库服务端口号冲突，修改ceilometer和heat端口号


