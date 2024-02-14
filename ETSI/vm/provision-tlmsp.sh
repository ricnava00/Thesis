#!/bin/bash
function log {
	echo -e "[INFO] $1"
}

function logerr {
	echo -e "[ERRO] $1"
}

log "Upgrade packages"
apt-get update -qq \
	&& apt-get upgrade -qq \
	|| exit 1

log "Install nice-to-haves"
apt-get install -qq \
		bash-completion \
		command-not-found \
	|| exit 1

log "Install dependencies"
apt-get install -qq \
		autoconf \
		clang \
		gettext \
		libexpat1-dev \
		libpcre3-dev \
		libpcre2-dev \
		libtool-bin \
		libev-dev \
		make \
		parallel \
		pkg-config \
		python-is-python3 \
	|| exit 1

pip install -q jsonschema matplotlib networkx \
  || exit 1

log "Building TLMSP-tools"
cp -r /home/vagrant/shared/TLMSP tlmsp
cd tlmsp/tlmsp-tools
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
openssl_repo=https://github.com/ricnava00/tlmsp-openssl.git #https://forge.etsi.org/rep/cyber/tlmsp-openssl.git
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

if ! gcc --version | awk '/gcc/ && ($3+0)>=11{err=1}END{exit err}'
then
  echo "\e[31mApplying gcc 11 fixes before building\e[0m"
  sleep 3
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
tar -C /home/vagrant/tlmsp -cf /home/vagrant/shared/tlmsp-compiled.tar install || exit 1
echo ". /home/vagrant/tlmsp/install/share/tlmsp-tools/tlmsp-env.sh" >> /home/vagrant/.bashrc
exit $ret