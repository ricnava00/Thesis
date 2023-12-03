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

#Copied from build.sh, download repos for modification before building
#---
# echo given message to stdout such that it stands out
announce() {
    echo ">>>" $@
}

# like announce, but for critical messages
alert() {
    echo "!!!" $@
}

require_success() {
    eval $@
    if [ $? -ne 0 ]; then
	alert "command failed:" $@
	exit 1
    fi
}

require_file() {
    local filename="$1"
    local fail_msg="$2"

    if [ ! -f ${filename} ]; then
	alert ${fail_msg}
	exit 1
    fi
}

require_repo() {
    local destdir="$1"
    local repo="$2"
    local branch_or_tag="$3"
    local origdir

    origdir=$(pwd)
    if [ ! -d ${destdir} ]; then
	announce "Cloning ${repo} to ${destdir}"
	require_success git clone ${repo} ${destdir}
	require_success cd ${destdir}
	announce "Checking out ${branch_or_tag}"
	require_success git checkout ${branch_or_tag}
    else
	announce "Repo ${repo} appears to already be cloned to ${destdir}"
    fi
    cd ${origdir}
}

build_script_dir=$(pwd)
require_file "${build_script_dir}/$(basename $0)" \
	     "This script is intended to be run from the directory that contains it"

tlmsp_tools_dir=$(realpath ${build_script_dir}/..)
src_root=$(realpath ${tlmsp_tools_dir}/..)

openssl_dir=${src_root}/tlmsp-openssl
openssl_repo=https://forge.etsi.org/rep/cyber/tlmsp-openssl.git
openssl_branch_or_tag=master-tlmsp

curl_dir=${src_root}/tlmsp-curl
curl_repo=https://forge.etsi.org/rep/cyber/tlmsp-curl.git
curl_branch_or_tag=master-tlmsp

apache_httpd_dir=${src_root}/tlmsp-apache-httpd
apache_httpd_repo=https://forge.etsi.org/rep/cyber/tlmsp-apache-httpd.git
apache_httpd_branch_or_tag=master-tlmsp

# dir set after overrides below
apache_apr_repo=https://github.com/apache/apr.git
apache_apr_branch_or_tag=1.7.0

# dir set after overrides below
apache_apr_util_repo=https://github.com/apache/apr-util.git
apache_apr_util_branch_or_tag=1.6.1

pki_public=${install_dir}/etc/pki
pki_private=${install_dir}/etc/pki/private

# If available, load overrides for default source tree and tag/branch
# names
if [ -f ./local-build-config.sh ]; then
    . ./local-build-config.sh
fi
apache_apr_dir=${apache_httpd_dir}/srclib/apr
apache_apr_util_dir=${apache_httpd_dir}/srclib/apr-util

# Fetch all sources
for s in openssl curl apache_httpd apache_apr apache_apr_util; do
    eval destdir=\$${s}_dir
    eval repo=\$${s}_repo
    eval branch_or_tag=\$${s}_branch_or_tag

    announce "Fetching ${repo} (${branch_or_tag}) to ${destdir}"
    require_repo ${destdir} ${repo} ${branch_or_tag}
done
#---

#Apply patches

#Fixes bug: the part of the container after a match would be deleted instead of forwarded
patch -N -d${src_root} -p0 << EOF
--- tlmsp-tools/libdemo/activity.c	2023-12-02 15:07:55.286156961 +0000
+++ tlmsp-tools/libdemo/activity.c	2023-12-02 15:07:55.286156961 +0000
@@ -1515,6 +1515,8 @@
 		    TLMSP_container_context(new_container),
 		    TLMSP_container_length(new_container));
 		container_queue_add_head(read_q, new_container);
+		if(match_range->last==match_range->first)
+			match_range->last = container_queue_head_entry(read_q);
 		match_range->first = container_queue_head_entry(read_q);
 		match_range->first_offset = 0;
 	}
EOF

#Retry on "connection to client knows middlebox id, but to server does not", the check happens too early and a later received packet resolves it
patch -N -d${src_root} -p0 << EOF
--- tlmsp-openssl/ssl/tlmsp_mbx.c	2023-11-22 14:31:06.336866416 +0000
+++ tlmsp-openssl/ssl/tlmsp_mbx.c	2023-11-22 14:31:06.336866416 +0000
@@ -72,6 +72,7 @@
          */
         if (toserver->tlmsp.self == NULL && toclient->tlmsp.self != NULL) {
             fprintf(stderr, "%s: connection to client knows middlebox id, but to server does not.\n", __func__);
+            continue;
         }

         rv[1] = tlmsp_middlebox_handshake_half(toserver, toclient, 1, &error[1]);
EOF

if ! gcc --version | awk '/gcc/ && ($3+0)>=11{err=1}END{exit err}'
then
	echo "\e[31mApplying gcc 11 fixes before building\e[0m"
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
fi
./build.sh
ret=$?
chmod 777 -R /home/vagrant/tlmsp
tar -C /home/vagrant/tlmsp -cf /home/vagrant/shared/tlmsp-compiled-22.04.tar install || exit 1
echo ". /home/vagrant/tlmsp/install/share/tlmsp-tools/tlmsp-env.sh" >> /home/vagrant/.bashrc
exit $ret