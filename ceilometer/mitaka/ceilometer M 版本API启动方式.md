
[TOC]

ceilometer API实现了查询数据库信息（需要在ceilometer中进行数据库配置）的RESTful API。本文基于ubuntu进行描述。

## ceilometer API启动方式概述
ceilometer API是基于HTTP协议，使用JSON格式的RESTful API。其python应用程序与web服务器的交互符合WSGI规范，而API的应用程序提供了基于apache2和cmd的两种启动方式。

## 基于apache2启动ceilometer API
Apache没有内置WSGI的支持，通过扩展模块mod_wsgi来支持WSGI。Apache和mod_wsgi之间通过程序内部接口传递信息，mod_wsgi会实现WSGI的server端、进程管理以及对application的调用。
1、apache2的配置
/etc/apache2/sites-available/ceilometer.conf
该文件可以直接拷贝ceilometer源码中ceilometer/etc/apache2/ceilometer，设置了WSGI应用程序的端口、启动入口、进程组等信息：
```bash
# 端口
Listen 8777

<VirtualHost *:8777>
    WSGIDaemonProcess ceilometer-api processes=2 threads=10 user=SOMEUSER display-name=%{GROUP}
    WSGIProcessGroup ceilometer-api
    # 应用程序入口
    WSGIScriptAlias / /var/www/ceilometer/app
    WSGIApplicationGroup %{GLOBAL}
    <IfVersion >= 2.4>
        ErrorLogFormat "%{cu}t %M"
    </IfVersion>
    ErrorLog /var/log/httpd/ceilometer_error.log
    CustomLog /var/log/httpd/ceilometer_access.log combined
</VirtualHost>

WSGISocketPrefix /var/run/httpd

```
2、应用程序入口
/var/www/ceilometer/app
该文件可以直接拷贝ceilometer源码中ceilometer/ceilometer/api/app.wsgi
```python
"""Use this file for deploying the API under mod_wsgi.

See http://pecan.readthedocs.org/en/latest/deployment.html for details.
"""
from ceilometer import service
from ceilometer.api import app

# Initialize the oslo configuration library and logging
service.prepare_service([])
application = app.load_app()

```
3、以上设置好后，就可以重启apache服务了。
```
systemctl restart apache2.service
```
到此，ceilometer-api就启动成功了。
4、python应用程序中的启动代码
在2中，生成的application调用的代码：ceilometer/ceilometer/api/app.py
```python
def load_app():
    # Build the WSGI app
    # python应用程序使用PasteDeploy部署，这里导入PasteDeploy的配置文件，并部署app
    cfg_file = None
    cfg_path = cfg.CONF.api_paste_config
    if not os.path.isabs(cfg_path):
        cfg_file = CONF.find_file(cfg_path)
    elif os.path.exists(cfg_path):
        cfg_file = cfg_path

    if not cfg_file:
        raise cfg.ConfigFilesNotFoundError([cfg.CONF.api_paste_config])
    LOG.info("Full WSGI config used: %s" % cfg_file)
    return deploy.loadapp("config:" + cfg_file)

```
## 基于cmd启动ceilometer API
1、cmd的入口设置文件：ceilometer/setup.cfg
```
console_scripts =
    ceilometer-api = ceilometer.cmd.api:main
```
2、ceilometer/cmd/api.py
```python
def main():
    service.prepare_service()
    app.build_server()
```
3、ceilometer/ceilometer/api/app.py
```python
def build_server():
    # 这里就走到了和apache启动相同的地方--使用PasteDeploy部署app
    app = load_app()
    # Create the WSGI server and start it
    # 与apache不同的地方，在代码中设置地址和端口，并启动
    host, port = cfg.CONF.api.host, cfg.CONF.api.port

...
    serving.run_simple(cfg.CONF.api.host, cfg.CONF.api.port,
                       app, processes=CONF.api.workers)
```
## ceilometer API 应用的启动流程
ceilometer API 应用使用PasteDeploy部署，这里需要上面代码中传入的paste.ini配置文件，理解这个文件，是理解Paste框架的重点。paste.ini文件的格式类似于INI格式，每个section的格式为[type:name]。这里重要的是理解几种不同type的section的作用。

    app: 这种section表示具体的app。
    filter: 实现一个过滤器中间件。
    pipeline: 用来把把一系列的filter串起来，最后一个必须是app

ceilometer源码路径为：ceilometer/etc/ceilometer/api_paste.ini
```
[pipeline:main]
pipeline = cors request_id authtoken api-server

[app:api-server]
paste.app_factory = ceilometer.api.app:app_factory

[filter:authtoken]
paste.filter_factory = keystonemiddleware.auth_token:filter_factory

[filter:request_id]
paste.filter_factory = oslo_middleware:RequestId.factory

[filter:cors]
paste.filter_factory = oslo_middleware.cors:filter_factory
oslo_config_project = ceilometer
```
从上面流程看，知道启动过程为ceilometer.api.app:app_factory-->setup_app
```python
def setup_app(pecan_config=None):
    # FIXME: Replace DBHook with a hooks.TransactionHook
    # hooks的作用类似于WSGI中间件，这里注意DBHook()，用来设置api连接数据库
    app_hooks = [hooks.ConfigHook(),
                 hooks.DBHook(),
                 hooks.NotifierHook(),
                 hooks.TranslationHook()]

    #  pecan用于实现app框架，框架的主要作用是实现路由
    pecan_config = pecan_config or {
        "app": {
             # 这里设置了路由入口
            'root': 'ceilometer.api.controllers.root.RootController',
            'modules': ['ceilometer.api'],
        }
    }

    pecan.configuration.set_config(dict(pecan_config), overwrite=True)
...
    # 应用pecan框架启动app
    app = pecan.make_app(
        pecan_config['app']['root'],
        debug=pecan_debug,
        hooks=app_hooks,
        wrap_app=middleware.ParsableErrorMiddleware,
        guess_content_type_from_ext=False
    )

    return app
```