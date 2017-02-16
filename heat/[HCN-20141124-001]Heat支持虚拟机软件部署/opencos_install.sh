# !/bin/bash

function init_dir()
{
    dst=$1
    if [ -d $dst ]; then
        rm -f $dst/*
    else
        mkdir -p $dst
    fi
}

workspace=`pwd`
result_path=$workspace/result
init_dir $result_path
target_bin=$1
export HOME=/root

./$target_bin --noexec --target $workspace/tmp/
cp $workspace/tmp/ans.txt /home/opencos_install/
#rm -rf  $workspace/tmp/

def_gw_if=`route | grep default | awk -F' ' '{print $8}'|uniq`
public_ip=""
if [[ -n "$def_gw_if" ]];then
    public_ip=`ifconfig "$def_gw_if" | grep 'inet ' | cut -d: -f2 | awk '{ print $2}'`
fi
sed s/CONFIG_HORIZON_HOST=.*/CONFIG_HORIZON_HOST=$public_ip/ -i /home/opencos_install/ans.txt

sed s/CONFIG_REPO=.*/CONFIG_REPO=/ -i /home/opencos_install/ans.txt

chmod +x $target_bin

echo "clean the environment..."
./$target_bin clean 1>>$result_path/clean.log 2>>$result_path/clean.err
if grep "Complete!" $result_path/clean.log
    then
        echo "clean successfully..."
else
    echo "clean failed, skip it ..."
fi

echo "installing, please wait for more than ten minutes...."

cd /etc/yum.repos.d/
rm -rf *
rm -rf /var/lib/puppet/*
cd $workspace/
./$target_bin install  -y
#1>>$result_path/install.log 2>>$result_path/install.err

if grep "Installation completed successfully" $result_path/install.log
    then
        echo "Installation completed successfully..."
else
    echo "Installation fail..."
    exit 0
fi
