#!/bin/bash
if [[ ! -f /home/vagrant/shared/tlmsp-compiled-20.04.tar ]]
then
	echo "Compiled 20.04 TLMSP binaries missing in shared folder! Did you start the 20.04 vm?"
	exit 1
fi
apt-get update
apt-get upgrade -y
apt-get install -y bash-completion command-not-found
apt-get install -y autoconf clang gettext libexpat1-dev libpcre3-dev libpcre2-dev libtool-bin libev-dev make parallel pkg-config python-is-python3
mkdir tlmsp
cd tlmsp
git clone https://forge.etsi.org/rep/cyber/103523_MSP/tlmsp/tlmsp-tools.git
cd tlmsp-tools
cd build
./build.sh
ret=$?
if [ $ret -ne 0 ]
then #Expected for Ubuntu 22.04
	echo "\e[31mBuild error, applying gcc 11 fixes\e[0m"
	sleep 3
	sed -i 's/my $gcc_devteam_warn = /my $gcc_devteam_warn = "-Wno-array-parameter "\n\t. /' ../../tlmsp-openssl/Configure
	sed -i 's/AM_CFLAGS = -Wall -Wextra/AM_CFLAGS = -Wall -Wextra -Wno-unused-but-set-variable/' ../Makefile.am
	cd ../../tlmsp-apache-httpd
	git clean -f
	git reset --hard
	git remote add fixUbuntu22 https://github.com/apache/apr.git
	git fetch fixUbuntu22
	git cherry-pick -n 0a763c5e500f4304b7c534fae0fad430d64982e8
	git remote remove fixUbuntu22
	cd srclib/apr
	git clean -f
	git reset --hard
	git remote add fixUbuntu22 https://github.com/apache/apr.git
	git fetch fixUbuntu22
	git cherry-pick -n 0a763c5e500f4304b7c534fae0fad430d64982e8
	git remote remove fixUbuntu22
	cd ../../../tlmsp-tools/build
	sed -i '75i\ \ \ \ \ \ \ \ \ \ \ \ continue;' ../../tlmsp-openssl/ssl/tlmsp_mbx.c #Retry on "connection to client knows middlebox id", the check happens too early and a later received packet resolves it
	./build.sh
	ret=$?
else #Expected for Ubuntu 20.04
	#As above, but rebuild openssl manually since all other components were already built successfully
	cd ../../tlmsp-openssl
	sed -i '75i\ \ \ \ \ \ \ \ \ \ \ \ continue;' ssl/tlmsp_mbx.c
	make -j16 && make install -j16
	ret=$?
fi
chmod 777 -R /home/vagrant/tlmsp
tar -C /home/vagrant/tlmsp -cf /home/vagrant/shared/tlmsp-compiled-22.04.tar install || exit 1
echo ". /home/vagrant/tlmsp/install/share/tlmsp-tools/tlmsp-env.sh" >> /home/vagrant/.bashrc
exit $ret