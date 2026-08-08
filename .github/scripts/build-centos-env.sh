#!/usr/bin/env bash
set -euo pipefail

jobs="${JOBS:-2}"
parallelism="${BUILDKIT_MAX_PARALLELISM:-2}"
builder_name="${BUILDKIT_BUILDER_NAME:-tdesktop-ci-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}-$$}"
config_path="$(mktemp)"
dockerfile_path="$(mktemp)"
patched_dockerfile_path="$(mktemp)"
dnf_retry_snippet_path="$(mktemp)"
git_retry_snippet_path="$(mktemp)"

cleanup() {
	docker buildx rm "$builder_name" >/dev/null 2>&1 || true
	rm -f "$config_path" "$dockerfile_path" "$patched_dockerfile_path" "$dnf_retry_snippet_path" "$git_retry_snippet_path"
}

trap cleanup EXIT

cat > "$config_path" <<EOF
[worker.oci]
  max-parallelism = $parallelism
EOF

cd Telegram/build/docker/centos_env
bash ../../../../.github/scripts/ci-retry.sh poetry install
docker buildx rm "$builder_name" >/dev/null 2>&1 || true
docker buildx create \
	--name "$builder_name" \
	--driver docker-container \
	--driver-opt network=host \
	--config "$config_path" \
	--use
docker buildx inspect --bootstrap
DEBUG="${DEBUG-}" LTO="${LTO-}" JOBS="$jobs" poetry run gen_dockerfile > "$dockerfile_path"
perl -0pi -e 's{^(\s*(?:RUN\s+|&&\s+)?)dnf\b}{$1dnf-retry}mg; s{\bgit clone\b}{git-retry clone}g; s{\bgit fetch\b}{git-retry fetch}g; s{curl -sSL}{curl --retry 5 --retry-delay 10 --connect-timeout 30 -fL -sS}g' "$dockerfile_path"
perl -0pi -e 's{git submodule update --init --recursive --depth=1([^\\\n]*) \\}{(git submodule sync --recursive; for attempt in 1 2 3; do git -c submodule.fetchJobs=1 submodule update --init --recursive --depth=1$1 && exit 0; sleep \$((attempt * 20)); done; git -c submodule.fetchJobs=1 submodule update --init --recursive$1) \\}g' "$dockerfile_path"
cat > "$dnf_retry_snippet_path" <<'EOF'
RUN cat <<'SCRIPT' > /usr/local/bin/dnf-retry && chmod +x /usr/local/bin/dnf-retry
#!/usr/bin/env bash
set -uo pipefail
attempt=1
status=0
while [ "$attempt" -le 4 ]; do
	if dnf "$@"; then
		exit 0
	else
		status=$?
	fi
	if [ "$attempt" -eq 4 ]; then
		exit "$status"
	fi
	sleep $((20 * attempt))
	attempt=$((attempt + 1))
done
exit "$status"
SCRIPT
EOF
cat > "$git_retry_snippet_path" <<'EOF'
RUN cat <<'SCRIPT' > /usr/local/bin/git-retry && chmod +x /usr/local/bin/git-retry
#!/usr/bin/env bash
set -uo pipefail
attempts="${GIT_RETRY_ATTEMPTS:-4}"
delay="${GIT_RETRY_DELAY_SECONDS:-20}"
attempt=1
status=0
while [ "$attempt" -le "$attempts" ]; do
	if git "$@"; then
		exit 0
	else
		status=$?
	fi
	if [ "$attempt" -eq "$attempts" ]; then
		exit "$status"
	fi
	sleep $((delay * attempt))
	attempt=$((attempt + 1))
done
exit "$status"
SCRIPT
RUN git config --global advice.detachedHead false \
	&& git config --global fetch.parallel 1 \
	&& git config --global submodule.fetchJobs 1 \
	&& git config --global http.version HTTP/1.1 \
	&& git config --global http.lowSpeedLimit 1000 \
	&& git config --global http.lowSpeedTime 60
EOF
awk -v dnfSnippet="$dnf_retry_snippet_path" -v gitSnippet="$git_retry_snippet_path" '
	{ print }
	!dnfInserted && /^FROM .* AS builder$/ {
		while ((getline line < dnfSnippet) > 0) {
			print line
		}
		close(dnfSnippet)
		dnfInserted = 1
	}
	!gitInserted && $0 == "WORKDIR /usr/src" {
		while ((getline line < gitSnippet) > 0) {
			print line
		}
		close(gitSnippet)
		gitInserted = 1
	}
	END {
		if (!dnfInserted || !gitInserted) {
			exit 1
		}
	}
' "$dockerfile_path" > "$patched_dockerfile_path"
mv "$patched_dockerfile_path" "$dockerfile_path"
docker buildx build \
	--builder "$builder_name" \
	--load \
	--progress=plain \
	-t tdesktop:centos_env - < "$dockerfile_path"
