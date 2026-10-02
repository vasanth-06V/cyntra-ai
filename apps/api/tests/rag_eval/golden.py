"""Golden resumes and job descriptions for the retrieval/ATS eval harness.

Resumes deliberately differ in layout (heading styles, ALL-CAPS, bullets,
inline skill lists, a multi-column garble) because layout is where chunking
breaks. Each JD lists the requirements the extractor is expected to produce;
`EVIDENCE` records, per resume, which requirements it genuinely covers.
"""

STRONG_BACKEND = """Jane Doe
Senior Backend Engineer | jane.doe@example.com | +1 415 555 0134

Summary
Backend engineer with 8 years of experience building payment and data platforms in Python.

Experience
Staff Engineer, Acme Payments (2020 - Present)
- Led migration of a Django monolith to services deployed on Kubernetes (EKS) on AWS.
- Designed PostgreSQL schemas and tuned queries, cutting p95 latency from 800ms to 120ms.
- Containerised all services with Docker and built CI pipelines in GitHub Actions.
- Introduced Redis caching for hot read paths.

Backend Engineer, DataCo (2016 - 2020)
- Built ETL pipelines in Python and SQL processing 2TB per day.
- Mentored four junior engineers and ran the on-call rotation.

Education
BS Computer Science, State University, 2016

Skills
Python, Django, PostgreSQL, Docker, Kubernetes, AWS, Redis, Terraform, GitHub Actions
"""

CAPS_STYLE = """MARCUS LEE
Platform Engineer
marcus.lee@example.com  |  (212) 555-0188

PROFESSIONAL EXPERIENCE
Platform Engineer - Northwind Logistics                                  2019 - Present
• Operate production Kubernetes clusters serving 40 microservices written in Python and Go.
• Own the PostgreSQL fleet: backups, failover, and capacity planning.
• Packaged services with Docker and automated releases with Terraform.

Systems Administrator - Contoso                                          2015 - 2019
• Managed Linux servers and a private cloud; introduced infrastructure as code.

TECHNICAL SKILLS & TOOLS
Languages: Python, Go, Bash
Platforms: Kubernetes, Docker, AWS, Terraform
Data: PostgreSQL, Redis

EDUCATION
BSc Information Systems, City College, 2015
"""

WEAK_UNRELATED = """Priya Natarajan
Marketing Manager
priya.n@example.com

Summary
Marketing manager with 6 years of experience running digital campaigns and growing brand awareness.

Experience
Marketing Manager, BrightLeaf (2019 - Present)
- Planned and executed SEO, email and social campaigns that grew leads by 60%.
- Managed a 200k annual budget and agency relationships.
- Reported on funnel performance in Salesforce and Google Analytics.

Marketing Coordinator, Fresh Co (2016 - 2019)
- Produced content calendars and coordinated product launches.

Education
BA Communications, Lakeside University, 2016

Skills
SEO, Content strategy, Salesforce, Google Analytics, Copywriting
"""

JUNIOR_PARTIAL = """Tom Alvarez
Junior Developer
tom.alvarez@example.com | 555-0142

Experience
Junior Developer, SmallShop (2023 - Present)
- Built internal tools in Python and SQL.
- Wrote unit tests and fixed bugs in a Flask application.
- Helped migrate a MySQL database to PostgreSQL.

Intern, Local Bank (2022)
- Automated spreadsheet reports with Python scripts.

Education
BS Computer Science, Tech Institute, 2022

Skills
Python, SQL, Flask, Git, PostgreSQL
"""

MESSY_LAYOUT = """SAM OKAFOR   sam.okafor@example.com   555 0199
Work History & Projects
2021 - now   Full stack developer at Orbit Labs. Built dashboards in React and TypeScript
and REST APIs in Python (FastAPI) backed by PostgreSQL. Deployed with Docker on AWS.
2018 - 2021  Developer at Pixel Forge. Built a Django app, wrote SQL reports.
Languages & Frameworks:  Python, TypeScript, React, FastAPI, Django, SQL
Tools:  Docker, AWS, Git, Jenkins
Education: BSc Software Engineering, 2018
"""

FRONTEND_DEV = """Alicia Brandt
Frontend Developer
alicia.brandt@example.com | 555-0171

Summary
Frontend developer focused on accessible, fast interfaces in React and TypeScript.

Experience
Senior Frontend Developer, PixelWorks (2020 - Present)
- Built a design system in React and TypeScript used by 12 product teams.
- Improved Lighthouse performance scores from 54 to 96 with code splitting and image optimisation.
- Wrote accessible CSS (Tailwind and CSS modules) and led WCAG audits.

Frontend Developer, ShopLoop (2017 - 2020)
- Implemented checkout flows in React and Redux; wrote Jest and Cypress tests.

Education
BS Computer Science, Metro University, 2017

Skills
React, TypeScript, JavaScript, CSS, Tailwind, Jest, Cypress, Redux, HTML
"""

RESUMES = {
    "strong_backend": STRONG_BACKEND,
    "caps_style": CAPS_STYLE,
    "weak_unrelated": WEAK_UNRELATED,
    "junior_partial": JUNIOR_PARTIAL,
    "messy_layout": MESSY_LAYOUT,
    "frontend_dev": FRONTEND_DEV,
}

# What the requirements extractor should return for each JD.
JDS = {
    "backend": {
        "title": "Senior Backend Engineer",
        "must_have": ["Python", "PostgreSQL", "Docker", "Kubernetes"],
        "nice_to_have": ["AWS", "Redis", "Django"],
    },
    "frontend": {
        "title": "Senior Frontend Engineer",
        "must_have": ["React", "TypeScript", "CSS"],
        "nice_to_have": ["Jest", "Redux"],
    },
}

# resume -> jd -> requirements that resume genuinely covers (by lowercase surface term).
EVIDENCE: dict[str, dict[str, set[str]]] = {
    "strong_backend": {"backend": {"python", "postgresql", "docker", "kubernetes", "aws", "redis", "django"}},
    "caps_style": {"backend": {"python", "postgresql", "docker", "kubernetes", "aws", "redis"}},
    "weak_unrelated": {"backend": set(), "frontend": set()},
    "junior_partial": {"backend": {"python", "postgresql"}},
    "messy_layout": {"backend": {"python", "postgresql", "docker", "aws", "django"}},
    "frontend_dev": {"frontend": {"react", "typescript", "css", "jest", "redux"}},
}

# Headings a good chunker must find, per resume (lowercase, matched as substrings
# of the section label it assigns).
EXPECTED_SECTIONS: dict[str, list[str]] = {
    "strong_backend": ["summary", "experience", "education", "skills"],
    "caps_style": ["experience", "skills", "education"],
    "weak_unrelated": ["summary", "experience", "education", "skills"],
    "junior_partial": ["experience", "education", "skills"],
    "messy_layout": ["experience", "skills", "education"],
    "frontend_dev": ["summary", "experience", "education", "skills"],
}

# (resume, jd) pairs that must rank: every "strong" should outscore every "weak".
RANKING = {
    "backend": {
        "strong": ["strong_backend", "caps_style"],
        "middle": ["messy_layout", "junior_partial"],
        "weak": ["weak_unrelated", "frontend_dev"],
    },
    "frontend": {
        "strong": ["frontend_dev"],
        "middle": ["messy_layout"],
        "weak": ["weak_unrelated", "strong_backend"],
    },
}
