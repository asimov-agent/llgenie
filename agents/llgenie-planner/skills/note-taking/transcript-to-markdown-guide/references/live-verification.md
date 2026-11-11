# Live verification of a guide's commands (opt-in, tier 5)

Use only when the user has asked for proof that the guide's commands actually work, or
accepted an offer to test them. Everything here changes host state, so ask first and
tear down after. The payoff is real: static checks cannot catch a default that changed
since the lecture was recorded, and that is the error class that survives every other
check.

## What tier 5 uniquely catches

A lecture states a default that was true for its controller/runtime version. Static
analysis sees a valid object; only execution shows the behaviour changed. Examples from
a real pass over an ingress lab guide:

| Claim inherited from the lecture | What execution showed |
|---|---|
| `kubectl create ingress … --rule=…` (no class) works | Modern controller **ignores** a classless Ingress: request 404s, `describe` looks perfect, one warning in the controller log |
| `ssl-redirect` (default `true`) sends HTTP to HTTPS | Inert without `spec.tls`; the redirect needs `force-ssl-redirect: "true"` |
| `rewrite-target: /` is required for prefix routing | Only needed when the backend 404s on the prefixed path; a catch-all server answers 200 without it |
| Setting `ssl-redirect: "false"` fixes the loop | Does **not** override `force-ssl-redirect` — that annotation must be removed |

When a claim turns out to be version-dependent, write **both** in the guide (current
behaviour + the version the speaker had) rather than silently modernising the lecture.

## Recipe that worked (Kubernetes, Docker + kind on Linux)

```bash
# 1. tooling into a bin dir, not /usr/local/bin
mkdir -p ~/.local/bin
export PATH=$HOME/.local/bin:$PATH
curl -sSLo /tmp/kind    https://kind.sigs.k8s.io/dl/v0.24.0/kind-linux-amd64
curl -sSLo /tmp/kubectl https://dl.k8s.io/release/v1.31.1/bin/linux/amd64/kubectl
install -m755 /tmp/kind /tmp/kubectl ~/.local/bin/

# 2. cluster, publishing the NodePort the guide talks about
cat > /tmp/kind-ingress.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: verify
nodes:
  - role: control-plane
    extraPortMappings:
      - {containerPort: 30080, hostPort: 30080, protocol: TCP}
EOF
kind create cluster --config /tmp/kind-ingress.yaml --wait 120s

# 3. the component under test (here: ingress-nginx), exposed as a NodePort
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.2/deploy/static/provider/cloud/deploy.yaml
kubectl -n ingress-nginx wait --for=condition=Available deploy/ingress-nginx-controller --timeout=300s
kubectl -n ingress-nginx patch svc ingress-nginx-controller --type=merge \
  -p '{"spec":{"type":"NodePort","ports":[{"name":"http","port":80,"targetPort":"http","nodePort":30080}]}}'

# 4. exercise the guide's own commands, capture real output, then assert on it
curl -s -o /dev/null -D - http://localhost:30080/wear | grep -E 'HTTP/|Location'
kubectl -n ingress-nginx logs deploy/ingress-nginx-controller --tail=5
```

Reading results: the **status code plus the component's own log** is the evidence.
A 404 with `ignoring ingress … does not contain a valid IngressClass` identifies the
cause; a 308 with `Location: https://host/wear` (no port) proves the redirect target
is dead. Quote those two lines in the guide — they are what a reader will recognise.

## Teardown checklist (do all of it, then verify)

```bash
kind delete cluster --name verify
docker network ls --format '{{.Name}}' | grep -qx kind && docker network rm kind
rm -f ~/.local/bin/kind ~/.local/bin/kubectl /tmp/kind /tmp/kubectl
rm -rf ~/.kube                       # kind/kubectl discovery cache, if it did not exist before
rm -f <scratch>/kind-*.yaml
git worktree remove --force <path> && git branch -D <branch>   # if you checked a PR out
```

Then report: what was created, what was removed, and what is still there (a pulled
image in the local store, a service you did not start). Never leave the machine in a
different state from the one you found without saying so.
