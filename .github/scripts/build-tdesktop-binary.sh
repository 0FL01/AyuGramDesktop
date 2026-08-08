#!/usr/bin/env bash
set -euo pipefail

ci_retry() {
	local attempts="${CI_RETRY_ATTEMPTS:-4}"
	local delay="${CI_RETRY_DELAY_SECONDS:-20}"
	local attempt=1
	local status=0

	while [ "$attempt" -le "$attempts" ]; do
		echo "ci-retry: attempt $attempt/$attempts: $*"
		if "$@"; then
			return 0
		else
			status=$?
		fi
		if [ "$attempt" -eq "$attempts" ]; then
			return "$status"
		fi
		sleep $((delay * attempt))
		attempt=$((attempt + 1))
	done

	return "$status"
}

ci_retry dnf install -y ccache

export PATH="/usr/lib64/ccache:$PATH"
export CCACHE_DIR=/ccache
export CCACHE_BASEDIR=/usr/src/tdesktop
export CCACHE_COMPRESS=1
export CC='ccache gcc'
export CXX='ccache g++'

/usr/src/tdesktop/Telegram/build/docker/centos_env/build.sh \
	-D TDESKTOP_API_ID="${TDESKTOP_API_ID:?}" \
	-D TDESKTOP_API_HASH="${TDESKTOP_API_HASH:?}" \
	-D USE_CCACHE=ON

ccache -s
