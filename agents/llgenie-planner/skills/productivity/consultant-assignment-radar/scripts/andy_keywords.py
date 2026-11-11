"""Andy Holst's CV keyword profile — the matching vocabulary.

Derived from the CV's "Competencies in Focus", assignment tech lists and
"Assignments in Focus" narrative. Every keyword carries an alias list because
Swedish ads mix English/Swedish spellings ("lösningsarkitekt" vs "solution architect").

Structure:  GROUPS[group] = {"label": ..., "weight": 1..3, "terms": {display: [aliases]}}
Scoring lives in score_text() below — keep it the single source of truth for both
stage 1 (Platsbanken) and stage 2.5 (broker detail pages).
"""
import re

GROUPS = {
    "devsecops": {
        "label": "DevSecOps / DevOps / CI-CD",
        "weight": 3,
        "terms": {
            "DevSecOps": ["devsecops", "dev-sec-ops", "security in the pipeline", "säkerhet i pipeline"],
            "DevOps": ["devops"],
            "CI/CD": ["ci/cd", "cicd", "ci och cd", "continuous integration", "continuous delivery", "continuous deployment", "kontinuerlig integration"],
            "CI pipelines": ["pipeline", "pipelines", "byggpipeline"],
            "Jenkins": ["jenkins"],
            "GitHub Actions": ["github actions", "gh actions", "github-actions"],
            "GitLab CI": ["gitlab ci", "gitlab-ci", "gitlab pipelines"],
            "Argo CD": ["argo cd", "argocd", "argo-cd"],
            "GitOps": ["gitops", "git ops"],
            "Release automation": ["release automation", "releaseautomatisering", "deploy automation"],
            "Dagger": ["dagger"],
        },
    },
    "cloud": {
        "label": "Cloud & platform (AWS-heavy)",
        "weight": 3,
        "terms": {
            "AWS": ["aws", "amazon web services"],
            "AWS Lambda": ["lambda", "awslambda"],
            "AWS Fargate": ["fargate"],
            "AWS S3": ["s3", "s3-bucket"],
            "AWS EC2": ["ec2"],
            "AWS RDS": ["rds"],
            "AWS VPC": ["vpc"],
            "AWS Route 53": ["route 53", "route53"],
            "AWS ELB": ["elb", "elastic load balanc"],
            "AWS SQS": ["sqs"],
            "AWS SNS": ["sns topi", "amazon sns"],
            "AWS CloudWatch": ["cloudwatch"],
            "AWS Kinesis": ["kinesis"],
            "AWS SDK (boto3)": ["boto3", "aws sdk"],
            "Azure": ["azure"],
            "GCP": ["gcp", "google cloud"],
            "Serverless": ["serverless", "serverlös", "lambda-arkitektur"],
            "Cloud architecture": ["cloud architect", "molntjänst", "molnarkitekt", "cloud-arkitekt", "molntjänster"],
            "FinOps / cost optimisation": ["kostnadsoptimering", "finops"],
        },
    },
    "containers": {
        "label": "Kubernetes & containers",
        "weight": 3,
        "terms": {
            "Kubernetes": ["kubernetes", "k8s", "kube"],
            "Rancher / RKE": ["rancher", "rke1", "rke2", "rke "],
            "OpenShift": ["openshift"],
            "Helm": ["helm", "helm chart"],
            "Docker": ["docker", "dockerfile"],
            "Podman": ["podman"],
            "OCI containers": ["oci-image", "oci image", "container-avbildning", "container image", "containerisera"],
            "Service mesh": ["service mesh", "istio", "linkerd"],
            "Kustomize": ["kustomize"],
        },
    },
    "iac": {
        "label": "Infrastructure as Code",
        "weight": 3,
        "terms": {
            "Terraform": ["terraform"],
            "CloudFormation": ["cloudformation"],
            "Ansible": ["ansible"],
            "IaC": ["infrastructure as code", "infrastruktur som kod", "iac"],
            "Pulumi": ["pulumi"],
            "Golden paths / platform engineering": ["golden path", "internal developer platform", "idp ", "platform engineering", "plattformsarbete", "plattformsingenjör", "plattformsutvecklare"],
        },
    },
    "security": {
        "label": "Security engineering (Security first)",
        "weight": 3,
        "terms": {
            "Security architect": ["security architect", "säkerhetsarkitekt", "säkerhetsarkitektur"],
            "AppSec": ["appsec", "applikationssäkerhet", "application security"],
            "Cybersecurity": ["cyber security", "cybersäkerhet", "cyber-security"],
            "Information security": ["informationssäkerhet", "information security"],
            "IAM": ["iam", "identity and access management", "identitetshantering", "behörighetshantering"],
            "OAuth2 / OIDC": ["oauth", "oidc", "openid"],
            "Zero Trust": ["zero trust"],
            "PKI / TLS / CA": ["pki", "csr", "certificate authority", "x.509", "tls", "certifikathantering", "certifikat"],
            "OpenSSL": ["openssl"],
            "Kryptografi": ["kryptograf", "cryptograph", "encryption", "kryptering"],
            "Vulnerability scanning": ["sårbarhetsscan", "vulnerability", "trivy", "grype", "syft", "anchore", "snyk"],
            "Penetration testing": ["penetrationstest", "penetration test", "zap", "burp", "sqlmap", "nikto"],
            "SIEM / SOC": ["siem", "soc ", "sentinel", "defender xdr", "soar", "splunk", "qradar"],
            "Compliance": ["iso 27001", "nis2", "gdpr", "dataskydd", "regelefterlevnad", "compliance"],
            "SonarQube": ["sonarqube", "sonar"],
            "Vault / secrets": ["hashicorp vault", "vault", "secrets management"],
        },
    },
    "agentic_ai": {
        "label": "Agentic AI & Generative AI",
        "weight": 3,
        "terms": {
            "Agentic AI": ["agentic", "ai agent", "ai-agent", "autonoma agenter", "agent-orkestrering"],
            "LangChain / LangGraph": ["langchain", "langgraph"],
            "LLM": ["llm", "large language model", "språkmodell"],
            "Generative AI": ["generative ai", "generativ ai", "genai", "gen ai"],
            "RAG": ["rag ", "retrieval augmented", "vektor-databas", "vector database", "embeddings"],
            "Prompt engineering": ["prompt engineering", "promptning", "prompting"],
            "Copilot / coding agents": ["copilot", "opencode", "kilo code", "kiro", "cursor", "claude code", "codex"],
            "MLOps": ["mlops", "ml platform"],
            "Machine learning": ["machine learning", "maskininlärning", "ml engineer"],
            "AI governance / AI Act": ["ai act", "ai-governance", "ai governance", "ai-nyttjande"],
            "Inference servers": ["ollama", "llama.cpp", "vllm", "triton", "inference server"],
            "Hugging Face / open weights": ["hugging face", "huggingface", "open weight", "öppna modeller"],
            "Spec-driven development": ["spec-driven", "spec driven", "openspec", "spec kit", "speckit"],
        },
    },
    "architecture": {
        "label": "Solution architecture / Tech lead",
        "weight": 3,
        "terms": {
            "Solution architect": ["solution architect", "lösningsarkitekt", "solutionsarkitekt"],
            "IT / system architect": ["it-arkitekt", "it arkitekt", "systemarkitekt", "it arkitekt"],
            "Enterprise architect": ["enterprise architect", "verksamhetsarkitekt", "företagsarkitekt"],
            "Infrastructure architect": ["infrastrukturarkitekt", "infrastructure architect"],
            "Integration architect": ["integrationsarkitekt", "integration architect"],
            "Security architect role": ["säkerhetsarkitekt", "security architect"],
            "Tech lead": ["tech lead", "teknisk ledare", "technical lead", "team lead", "teamledare", "arkitekt och teamledare"],
            "Arkitekt (stem)": ["arkitekt", "architect"],
            "Utvecklare (stem)": ["utvecklare"],
            "Ingenjör (stem)": ["ingenjör", "engineer"],
            "Systems engineering": ["systems engineering", "systemteknik", "kravspårbarhet", "requirements traceability", "architecture as code", "requirements as code"],
            "Microservices": ["microservice", "mikrotjänst"],
            "Monolith to microservices": ["monolit", "legacy-modernisering", "modernisering av legacy", "modernisering"],
            "API design": ["rest api", "restful", "rest-", "openapi", "swagger", "graphql"],
            "Event-driven": ["event-driven", "eventdriven", "händelsedriven", "kafka", "jms"],
        },
    },
    "backend": {
        "label": "Backend (Java & Python)",
        "weight": 2,
        "terms": {
            "Java": ["java ", "java,", "java.", "java/", "(java", "javautvecklare", "java-utvecklare"],
            "Spring Boot": ["spring boot", "spring framework", "spring boot 3", "spring cloud"],
            "Java EE / Jakarta": ["java ee", "jakarta ee", "jee", "jax", "ejb"],
            "Kotlin": ["kotlin"],
            "Python": ["python"],
            "FastAPI": ["fastapi"],
            "Flask": ["flask"],
            "Groovy": ["groovy"],
            "Perl": ["perl"],
            "C++": ["c++", "c/c++"],
            "Bash / shell": ["bash", "shell script", "shellscript", "skalskript", "powershell"],
            "Makefile / Maven / Gradle": ["maven", "gradle", "makefile", "make "],
            "Node.js": ["node.js", "nodejs", "node "],
            "JavaScript / TypeScript": ["javascript", "typescript"],
            "App servers": ["jboss", "wildfly", "tomcat", "websphere", "weblogic"],
        },
    },
    "data": {
        "label": "Data & persistence",
        "weight": 2,
        "terms": {
            "PostgreSQL": ["postgres", "postgresql"],
            "MySQL": ["mysql", "mariadb"],
            "Oracle DB": ["oracle database", "oracle db", "oracledb"],
            "DB2": ["db2"],
            "Neo4j": ["neo4j", "grafdatabas", "graph database"],
            "JPA / Hibernate": ["jpa", "hibernate", "jakarta persistence", "persistence unit"],
            "Liquibase / Flyway / Alembic": ["liquibase", "flyway", "alembic"],
            "SQL": ["sql"],
            "Kafka": ["kafka"],
            "JMS": ["jms", "jakarta messaging", "message driven", "meddelandekö"],
            "Data engineering": ["data engineer", "dataplatform", "data platform", "datapipeline", "data pipeline", "etl", "elt", "spark", "flink", "dbt", "databricks", "snowflake"],
            "Redis": ["redis"],
            "MongoDB": ["mongodb", "mongo"],
        },
    },
    "observability": {
        "label": "Observability",
        "weight": 2,
        "terms": {
            "Prometheus": ["prometheus", "prometheus-operator", "promql"],
            "Grafana": ["grafana"],
            "Kibana / ELK": ["kibana", "elastic", "elk", "opensearch"],
            "Datadog": ["datadog"],
            "Monitoring / logging": ["monitoring", "övervakning", "observability", "loggning", "log analysis", "telemetri"],
            "Tracing": ["tracing", "jaeger", "opentelemetry", "otel"],
        },
    },
    "testing": {
        "label": "Testing & quality",
        "weight": 2,
        "terms": {
            "TDD / BDD": ["tdd", "bdd", "test driven", "testdriven", "beteendedriven"],
            "JUnit / Mockito": ["junit", "mockito", "powermock"],
            "Testcontainers": ["testcontainers"],
            "Automated testing": ["automatiserad testning", "automated test", "testautomation", "testautomatisering", "integrationstest", "e2e-test", "end-to-end test"],
            "Code quality gates": ["code coverage", "kodkvalitet", "code review", "kvalitetssäkring", "kodgranskning"],
            "JaCoCo / coverage": ["jacoco", "coverage"],
        },
    },
    "frontend": {
        "label": "Frontend (secondary)",
        "weight": 1,
        "terms": {
            "Angular": ["angular"],
            "React": ["react"],
            "HTML/CSS": ["html", "css"],
            "TypeScript UI": ["typescript ui", "tsx"],
        },
    },
    "methods": {
        "label": "Ways of working",
        "weight": 1,
        "terms": {
            "Agile / Scrum / Kanban": ["scrum", "agile", "agilt", "kanban", "sprint", "safe"],
            "Requirements / analysis": ["kravanalytiker", "kravanalys", "requirements", "kravställning", "kravspecifikation"],
            "Documentation as code": ["documentation as code", "docs-as-code", "dokumentation som kod", "markdown", "adr", "architecture description record"],
            "C4 / modelling": ["c4-modell", "c4 model", "plantuml", "structurizr", "likec4", "arkitekturmodellering"],
            "Confluence / Jira / wiki": ["jira", "confluence", "github wiki"],
            "Linux & OS": ["linux", "unix", "solaris", "debian", "ubuntu", "rhel", "gentoo", "arch linux", "bash-completion"],
            "Git & version control": ["git", "github", "gitlab", "bitbucket", "jenkins", "version control"],
            "Renovate / Dependabot": ["renovate", "dependabot"],
            "Public sector experience": ["myndighet", "offentlig sektor", "region ", "kommun", "regeringskansliet", "försäkringskassan", "polismyndigheten", "domstolsverket", "scb"],
        },
    },
}

# Headlines/roles outside Andy's domains — never written out, even if keywords leak in.
NOISE = re.compile(
    r"(sjuksköterska|lärare|förskollärare|elektriker|målare|kock|barnskötare|undersköterska|busschaufför|"
    r"tandläkare|veterinär|socialsekreterare|förskola|biostatistik|miljöinspektör|vaktmästare|städare|"
    r"\bios\b|android|frontendutvecklare|spelutveckl|unity|automotive|autosar|embedded|asic|"
    r"account manager|säljare|rekryterare|sales engineer)", re.I)


def compile_terms():
    """Terms whose display name ends in "(stem)" match as plain substrings, so Swedish compounds
    (Domänarkitekt, Systemutvecklare, DevSecOps-ingenjör, Säkerhetsarkitekt) are still caught."""
    out = {}
    for g, spec in GROUPS.items():
        out[g] = {}
        for disp, alts in spec["terms"].items():
            stem = disp.endswith("(stem)")
            pats = []
            for a in alts:
                a = a.strip()
                pats.append(re.compile(re.escape(a) if stem else r"(?<![a-zåäö0-9])" + re.escape(a), re.I))
            out[g][disp] = pats
    return out


TERMS = compile_terms()


def score_text(text: str):
    """Return (matched_keywords_by_group, group_scores, total_score).

    matched_keywords_by_group: {group: {display: [alias, ...]}}  (alias present in the text)
    total_score: weighted keyword count, groups capped so one noisy group cannot dominate.
    """
    low = " " + text.lower() + " "
    matched, group_scores = {}, {}
    for g, disp_map in TERMS.items():
        hits = {}
        for disp, patterns in disp_map.items():
            found = [p.pattern for p in patterns if p.search(low)]
            if found:
                hits[disp] = found
        if hits:
            matched[g] = hits
            cap = 6 if GROUPS[g]["weight"] >= 3 else 4
            group_scores[g] = min(len(hits), cap) * GROUPS[g]["weight"]
    return matched, group_scores, sum(group_scores.values())


def coverage(group_scores):
    """How many of the CV's core (weight-3) areas are represented."""
    core = [g for g, s in GROUPS.items() if s["weight"] == 3]
    return sum(1 for g in core if g in group_scores), len(core)
