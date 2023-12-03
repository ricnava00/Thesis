#!/bin/sh
#
# This script is for performing configuration, build, and install of
# TLMSP-enabled openssl, tlmsp-tools, and TLMSP-enabled apache and
# curl.
#
# The process is as follows:
#   - Obtain all missing sources

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
