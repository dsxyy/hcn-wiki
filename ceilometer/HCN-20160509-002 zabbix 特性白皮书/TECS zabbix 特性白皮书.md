# TECS ZABBIX 特性白皮书



——————中兴通讯云平台TECS2.0



- **法律声明**







若接收中兴通讯股份有限公司（以下称为“中兴通讯”）的此份文档，即表示您已同意以下条款。若不同意以下条款，请停止使用本文档。







本文档版权所有中兴通讯股份有限公司。保留任何未在本文档中明示授予的权利。文档中涉及中兴通讯的专有信息。未经中兴通讯事先书面许可，任何单位和个人不得复制、传递、分发、使用和泄漏该文档以及该文档包含的任何图片、表格、数据及其他信息。







**ZTE**和**ZTE中兴**是中兴通讯的注册商标。中兴通讯产品的名称和标志是中兴通讯的商标或注册商标。在本文档中提及的其他产品或公司名称可能是其各自所有者的商标或注册商标。在未经中兴通讯或第三方权利人事先书面同意的情况下，阅读本文档并不表示以默示、不可反言或其他方式授予阅读者任何使用本文档中出现的任何标记的权利。







本产品符合有关环境保护和人身安全方面的设计要求，产品的存放、使用和弃置应遵照产品手册、相关合同或相关国法律、法规的要求进行。







本文档按“现状”和“仅此状态”提供。本文档中的信息随着中兴通讯产品和技术的进步将不断更新，中兴通讯不再通知此类信息的更新。







- **中兴通讯股份有限公司**



**地址**:	中国深圳市科技南路55号



**邮编**:	518057



**网站**:	http://support.zte.com.cn



**邮箱**:	800@zte.com.cn











* * *







**目录**







[TOC]







## 1. 背景介绍



### 1.1 介绍



Zabbix是一个企业级的开源分布式监控解决方案。

TECS中，zabbix安装部署图如下：



![zabbix部署示意图.JPG](.\zabbix部署示意图.JPG)



zabbix-server可以单独安装在一个节点上，也可以安装在计算节点或控制节点上；zabbix使用mariadb数据库存储数据，现有实现是共用TECS的mariadb数据库。

zabbix-agent默认除了指定不安装的节点上，其它节点都安装；

现有实现没有考虑zabbix-proxy，上图中虚线框部分。



## 2. zabbix自动链接模板



### 2.1 概述

在安装TECS时，zabbix把所有节点分为以下三种：

- 控制节点：安装HA、LB和指定为TECS控制节点的节点

- 计算节点：指定为TECS计算节点的节点

- 合一节点: 包含以上两者的节点



根据上面所确定的节点类型链接不同的模板，监控不同的服务状态。



### 2.2 解决方案



在完成TECS安装后，节点自动加入zabbix监控中，并且分别链接以下模板：



#### 2.2.1 控制节点：



##### Template App NTP Service

监控NTP服务状态



##### Template App SSH Service

监控SSH服务状态



##### Template OS Linux

监控linux系统运行状态

Template App Zabbix Agent: Agent ping

Available memory

Checksum of /etc/passwd

Context switches per second

CPU user time

CPU nice time

CPU system time

CPU iowait time

CPU idle time

CPU interrupt time

CPU steal time

CPU softirq time

Free swap space

Free swap space in %

Host boot time

Host local time

Host name

Template App Zabbix Agent: Host name of zabbix_agentd running

Interrupts per second

Maximum number of opened files

Maximum number of processes

Number of logged in users

Number of processes

Number of running processes

Processor load (1 min average per core)

Processor load (5 min average per core)

Processor load (15 min average per core)

System information

System uptime

Total memory

Total swap space

Template App Zabbix Agent: Version of zabbix_agent(d) running



##### Template App HTTP Service

监控HTTP服务状态



##### Template App Openstack Control Node Service

监控TECS控制节点服务状态，在服务存在时，检查服务是否正常。

neutron-dhcp-agent

neutron-l3-agent

neutron-metadata-agent

neutron-openvswitch-agent

neutron-ovs-cleanup

neutron-pci-nic-switch-agent

neutron-server

openstack-ceilometer-alarm-evaluator

openstack-ceilometer-alarm-notifier

openstack-ceilometer-api

openstack-ceilometer-central

openstack-ceilometer-collector

openstack-ceilometer-mend

openstack-ceilometer-notification

openstack-cinder-api

openstack-cinder-scheduler

openstack-cinder-volume

openstack-glance-api

openstack-glance-registry

openstack-heat-api

openstack-heat-api-cfn

openstack-heat-engine

openstack-ironic-api

openstack-ironic-conductor

openstack-keystone

openstack-losetup

openstack-nova-api

openstack-nova-cert

openstack-nova-conductor

openstack-nova-consoleauth

openstack-nova-monitor

openstack-nova-novncproxy

openstack-nova-scheduler



#### 2.2.2 计算节点：



##### Template App NTP Service

监控NTP服务



##### Template App SSH Service

监控SSH服务



##### Template OS Linux



##### Template App Openstack Compute Node Service

监控TECS计算节点服务状态

openstack-ceilometer-compute

openstack-nova-compute

openstack-nova-storage



#### 2.2.3 合一节点：

监控TECS合一节点(包含控制节点和计算节点)服务状态

##### Template App NTP Service

##### Template App SSH Service

##### Template OS Linux

##### Template App HTTP Service

##### Template App Openstack Control Node Service

##### Template App Openstack Compute Node Service



## 3 监控处理流程

一次完整的监控流程可以简单描述为：

Host Groups->Hosts->Applications->Items->Triggers->Actions->Medias->User Groups->Users

![zabbix监控流程.JPG](.\zabbix监控流程.JPG)



整个流程也可以通过创建一个auto-discovery完成



## 4 自定义item



### 4.1 item



![zabbit_item处理.JPG](.\zabbit_item处理.JPG)



- Items：  创建监控项，可以自定义key 值

- Triggers：创建触发器，监控项达到报警的阈值

- Graphs： 添加图形

- Application：是item的集合，方便对item进行分组管理

- Template：包含application、item、trigger、graphs、screens、discovery、web的集合



### 4.2 自定义item

- 1）Key语法格式：UserParameter=key, command

- 2）传递参数，例如

`UserParameter=wc[*],grep -c "$2" $1`

表示把$2,$1 的传递给key，测试如下

 `zabbix_get -s 127.0.0.1 -k wc[/etc/passwd,root]`

说明：/etc/passwd 为$1,root 为$2,则key 最终运行的命令为grep -c root /etc/passwd

格式如下

如果[]中括号里面有多个参数选项的值，每一个参数用用逗号隔开

- 3）若UserParameter 的内容需要单独写一个配置文件，则修改如下配置

/etc/zabbix/zabbix_agentd.conf:

`Include=/etc/zabbix/zabbix_agentd.d/   #(item配置文件存放目录)`
然后在web页面创建item，key与1）中的key值保持一致





## 5应用场景







## 6客户利益







## 7主要缩略词语















