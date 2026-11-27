"""The Bramblewood Institute for Health Research: the words and numbers of the demo.

Everything here is invented. The people, units, vendors, and applications do not exist.
Well-known open-source technologies appear under their own names, because a portfolio
without them would not be believable, but every support date in the demo is invented and
set relative to the day the demo is built.
"""

from __future__ import annotations

ORGANIZATION = "Bramblewood Institute for Health Research"
DOMAIN = "bramblewood.example"

# code, name, kind, parent
UNITS = [
    ("BIH", "Bramblewood Institute for Health Research", "organization", None),
    ("PRES", "Office of the President", "office", "BIH"),
    ("CBIO", "Cancer Biology", "division", "BIH"),
    ("IMMU", "Immunology", "division", "BIH"),
    ("POPH", "Population Health", "division", "BIH"),
    ("COMP", "Computational Biology", "division", "BIH"),
    ("CLIN", "Clinical Research", "division", "BIH"),
    ("SR", "Shared Resources", "department", "BIH"),
    ("GEN", "Genomics Core", "core_facility", "SR"),
    ("BIOR", "Biorepository", "core_facility", "SR"),
    ("IMG", "Imaging Core", "core_facility", "SR"),
    ("FLOW", "Flow Cytometry Core", "core_facility", "SR"),
    ("RC", "Research Computing", "core_facility", "SR"),
    ("CLINIC", "Bramblewood Research Clinic", "clinic", "CLIN"),
    ("INF", "Infusion", "department", "CLINIC"),
    ("CLAB", "Clinical Laboratory", "department", "CLINIC"),
    ("RPH", "Research Pharmacy", "department", "CLINIC"),
    ("PA", "Patient Access", "department", "CLINIC"),
    ("ADM", "Administration", "department", "BIH"),
    ("IT", "Information Technology", "department", "ADM"),
    ("ITAPP", "Enterprise Applications", "team", "IT"),
    ("ITRES", "Research Applications", "team", "IT"),
    ("ITINF", "Infrastructure", "team", "IT"),
    ("ITEA", "Enterprise Architecture", "team", "IT"),
    ("SEC", "Information Security", "department", "ADM"),
    ("CPO", "Compliance and Privacy", "department", "ADM"),
    ("SPO", "Sponsored Programs", "department", "ADM"),
    ("FIN", "Finance", "department", "ADM"),
    ("HR", "Human Resources", "department", "ADM"),
    ("FAC", "Facilities", "department", "ADM"),
    ("COMMS", "Communications", "department", "ADM"),
    ("PHIL", "Philanthropy", "department", "ADM"),
    ("EDU", "Education and Training", "department", "BIH"),
]
LAB_DIVISIONS = {"CBIO": 6, "IMMU": 5, "POPH": 4, "COMP": 5, "CLIN": 4}

GIVEN = [
    "Ada", "Amara", "Anika", "Ari", "Bea", "Benedikt", "Cai", "Calla", "Dario", "Delphine",
    "Eamon", "Edda", "Elio", "Esme", "Farah", "Florin", "Greer", "Hollis", "Idris", "Ines",
    "Jasper", "Jun", "Kaia", "Kiran", "Lark", "Leif", "Linnea", "Lorcan", "Mabel", "Malik",
    "Marisol", "Milo", "Nadia", "Noor", "Odile", "Orrin", "Pascale", "Pell", "Quinn", "Rafa",
    "Rhea", "Ronan", "Saoirse", "Sefa", "Soren", "Tamsin", "Teo", "Thea", "Ulla", "Vida",
    "Wren", "Xavi", "Yara", "Yusuf", "Zelie", "Zubin", "Anouk", "Bram", "Cyra", "Dov",
]  # fmt: skip
FAMILY = [
    "Abernethy", "Achterberg", "Alcorn", "Amadi", "Arkwright", "Ballantyne", "Belmonte",
    "Birchall", "Brannock", "Castellane", "Cavanagh", "Chaudry", "Clewes", "Coulthard",
    "Dagenais", "Delacroix", "Dunmore", "Eastwick", "Ellery", "Farrant", "Fenwick", "Galloway",
    "Gaskell", "Haldane", "Harrowby", "Hollins", "Ibarra", "Ingleby", "Jarrow", "Kavanagh",
    "Kestrel", "Lachance", "Larkin", "Lindqvist", "Lockwood", "Maddox", "Marchetti", "Mendel",
    "Nakamura", "Nwosu", "Okonkwo", "Ormerod", "Penhale", "Quarrie", "Rasmussen", "Redfern",
    "Rookwood", "Salcedo", "Sandoval", "Siddiqui", "Strand", "Tallis", "Thorncliffe", "Treloar",
    "Underhill", "Varga", "Wainwright", "Westergaard", "Yardley", "Zielinski",
]  # fmt: skip

# key, name, title, unit, roles as (role, unit code or None), offered on the sign-in page
CAST = [
    ("admin", "Hollis Treloar", "IT Systems Administrator", "ITINF", [("admin", None)], True),
    ("portfolio", "Marisol Haldane", "Director, Enterprise Architecture and Portfolio", "ITEA",
     [("manager", None)], True),
    ("architect", "Idris Penhale", "Enterprise Architect", "ITEA", [("architect", None)], True),
    ("architect2", "Linnea Strand", "Solutions Architect", "ITEA", [("architect", None)], False),
    ("cio", "Odile Westergaard", "Chief Information Officer", "IT", [("leader", "IT")], True),
    ("clin_lead", "Ronan Achterberg", "Vice President, Clinical Research", "CLIN",
     [("leader", "CLIN")], True),
    ("res_steward", "Thea Ballantyne", "Manager, Research Applications", "ITRES",
     [("steward", "ITRES")], True),
    ("ent_steward", "Benedikt Galloway", "Manager, Enterprise Applications", "ITAPP",
     [("steward", "ITAPP")], False),
    ("rse", "Kiran Lockwood", "Research Software Engineer", "COMP", [], True),
    ("pm", "Saoirse Marchetti", "Product Manager", "ITAPP", [], False),
    ("auditor", "Florin Ingleby", "Internal Auditor", "PRES", [("auditor", None)], True),
    ("security", "Nadia Siddiqui", "Security Architect", "SEC", [], False),
    ("leaver", "Orrin Dunmore", "Senior Developer", "ITAPP", [], False),
]  # fmt: skip

ABOUT = {
    "admin": "Runs the installation: people, units, appearance, connectors.",
    "portfolio": "Runs the portfolio: decisions, snapshots, the program.",
    "architect": "Keeps capabilities, technologies, and vendors; assesses applications.",
    "cio": "Leads Information Technology and decides for its applications.",
    "clin_lead": "Leads Clinical Research and decides for the clinic's applications.",
    "res_steward": "Keeps the research applications current.",
    "rse": "Builds and keeps research software, alone more often than not.",
    "auditor": "Reads everything, changes nothing.",
}

# key, name, kind
VENDORS = [
    ("larkfield", "Larkfield Systems", "software_vendor"),
    ("cobaltine", "Cobaltine Software", "software_vendor"),
    ("meridian", "Meridian Labware", "software_vendor"),
    ("quillstone", "Quillstone", "software_vendor"),
    ("harborview", "Harborview Data", "software_vendor"),
    ("ashgrove", "Ashgrove Health Systems", "software_vendor"),
    ("pinecrest", "Pinecrest Learning", "software_vendor"),
    ("ledgerline", "Ledgerline", "software_vendor"),
    ("staffbright", "Staffbright", "software_vendor"),
    ("fieldnote", "Fieldnote Surveys", "software_vendor"),
    ("vialtrack", "Vialtrack", "software_vendor"),
    ("helixware", "Helixware", "software_vendor"),
    ("clearpane", "Clearpane Imaging", "software_vendor"),
    ("signalhill", "Signal Hill Networks", "service_provider"),
    ("oakmere", "Oakmere Hosting", "service_provider"),
    ("brightdesk", "Brightdesk", "software_vendor"),
    ("kitewing", "Kitewing Collaboration", "software_vendor"),
    ("granary", "Granary Grants", "software_vendor"),
    ("tallyho", "Tallyho Procurement", "software_vendor"),
    ("dovetail", "Dovetail Records", "software_vendor"),
    ("openmicro", "Open Microscopy Collective", "open_source_project"),
    ("biosuite", "Biosuite Project", "open_source_project"),
    ("redcliff", "Redcliff Consortium", "consortium"),
    ("northwold", "Northwold University", "partner_institution"),
    ("cinder", "Cinder Analytics", "software_vendor"),
    ("medlark", "Medlark", "software_vendor"),
    ("pillbox", "Pillbox Systems", "software_vendor"),
    ("calendra", "Calendra", "software_vendor"),
    ("keystone", "Keystone Identity", "software_vendor"),
    ("watchtower", "Watchtower Monitoring", "software_vendor"),
    ("stratus", "Stratus Cloud", "service_provider"),
]  # fmt: skip

# Where things run: key, name, kind, provider (a vendor's key), where it is.
PLATFORMS = [
    ("dc", "Campus data center", "data_center", None, "Main campus, lower level"),
    ("standby", "Standby site", "hosting_provider", "oakmere", "Oakmere Hosting, in another region"),
    ("cloud_ent", "Enterprise cloud account", "cloud_account", "stratus", "Western region"),
    ("cloud_res", "Research cloud account", "cloud_account", "stratus", "Western region"),
    ("hpc", "Research computing cluster", "cluster", None, "Main campus"),
    ("lab", "Lab workstations", "endpoints", None, "In the labs, beside the instruments"),
]  # fmt: skip
# What pays: key, name, kind, code, and the days from the build until it ends, if it does.
# Grants are added as the applications they pay for are found.
FUNDING = [
    ("it", "Information Technology operating budget", "operating", "CC-4100", None),
    ("research", "Research operations budget", "operating", "CC-2200", None),
    ("clinic", "Clinic operating budget", "operating", "CC-5100", None),
    ("admin", "Administration operating budget", "operating", "CC-1000", None),
    ("recharge", "Core facility recharge", "chargeback", "RC-3300", None),
    ("capital", "Clinical systems renewal", "capital", "CP-0412", 400),
]  # fmt: skip
# How an application's yearly cost divides, by where it comes from: category and share.
COST_SHARES = {
    "saas": [("license", 85), ("internal", 15)],
    "vendor_custom": [("license", 60), ("support", 25), ("internal", 15)],
    "commercial": [("license", 45), ("support", 20), ("hosting", 15), ("internal", 20)],
    "research_software": [("hosting", 20), ("internal", 80)],
}
OWN_SHARES = [("hosting", 25), ("internal", 75)]
# Contracts with a story: the application, and what is particular about its contract.
CONTRACT_STORIES = {
    # The decision is to keep it until the contract ends; the notice date is two weeks off.
    "Clinic Scheduler": {"ends": 75, "notice": 60, "auto_renews": True},
    # Health data under a subscription nobody put a data agreement behind.
    "Clinic Questionnaires": {"alone": True, "agreement": "missing", "ends": 300, "notice": 30},
    # Bought for everyone, used by a few.
    "Learning Management": {"licenses": 5000, "used": 1400, "ends": 520, "notice": 90},
}

# Technologies that only run on a workstation in the lab.
ON_A_WORKSTATION = {"matlab", "access"}

# key, name, kind, radar, releases as (cycle, days from the build its support ends, or None)
TECHNOLOGIES = [
    ("python", "Python", "language", "adopt",
     [("3.9", -390), ("3.11", 330), ("3.12", 700), ("3.13", 1060)]),
    ("r", "R", "language", "adopt", [("4.1", -200), ("4.3", 400), ("4.4", 760)]),
    ("java", "Java", "language", "trial", [("8", -500), ("11", 260), ("17", 1400), ("21", 2600)]),
    ("node", "Node.js", "runtime", "adopt", [("16", -800), ("18", -150), ("20", 160), ("22", 880)]),
    ("php", "PHP", "language", "hold", [("7.4", -1100), ("8.1", -20), ("8.3", 750)]),
    ("dotnet", ".NET", "framework", "trial", [("6", -380), ("8", 360)]),
    ("django", "Django", "framework", "adopt", [("3.2", -600), ("4.2", 140), ("5.2", 1200)]),
    ("react", "React", "framework", "adopt", [("17", None), ("18", None)]),
    ("angularjs", "AngularJS", "framework", "hold", [("1.8", -1400)]),
    ("spring", "Spring Boot", "framework", "trial", [("2.7", -560), ("3.3", 220)]),
    ("shiny", "Shiny", "framework", "adopt", [("1.8", None)]),
    ("postgres", "PostgreSQL", "database", "adopt",
     [("12", -380), ("13", 85), ("15", 1050), ("16", 1430)]),
    ("mysql", "MySQL", "database", "hold", [("5.7", -760), ("8.0", 120), ("8.4", 1800)]),
    ("mongodb", "MongoDB", "database", "assess", [("5.0", -400), ("7.0", 640)]),
    ("redis", "Redis", "database", "trial", [("7.2", 500)]),
    ("ubuntu", "Ubuntu", "operating_system", "adopt", [("18.04", -900), ("20.04", -200), ("22.04", 870), ("24.04", 1600)]),
    ("rhel", "Red Hat Enterprise Linux", "operating_system", "trial", [("7", -520), ("8", 950), ("9", 2000)]),
    ("winserver", "Windows Server", "operating_system", "hold", [("2012 R2", -1100), ("2016", 410), ("2022", 1800)]),
    ("kubernetes", "Kubernetes", "platform", "adopt", [("1.29", -150), ("1.31", 120), ("1.32", 300)]),
    ("tomcat", "Apache Tomcat", "middleware", "hold", [("8.5", -240), ("9", 900)]),
    ("nextflow", "Nextflow", "platform", "adopt", [("23", None), ("24", None)]),
    ("snakemake", "Snakemake", "platform", "trial", [("7", None), ("8", None)]),
    ("matlab", "MATLAB", "product", "hold", [("R2019b", -300), ("R2023b", 500)]),
    ("access", "Desktop database", "product", "hold", [("2013", -1000)]),
]  # fmt: skip

# Technologies the end-of-life connector matched, by their key in its dataset, and the latest
# version it read for some releases. The dates it read are the demo's own invented ones.
EOL_KEYS = {
    "python": "python", "node": "nodejs", "java": "oracle-jdk", "php": "php", "dotnet": "dotnet",
    "django": "django", "spring": "spring-boot", "angularjs": "angularjs",
    "postgres": "postgresql", "mysql": "mysql", "mongodb": "mongodb", "redis": "redis",
    "ubuntu": "ubuntu", "rhel": "rhel", "winserver": "windows-server",
    "kubernetes": "kubernetes", "tomcat": "tomcat", "matlab": "matlab",
}  # fmt: skip
EOL_MISSING = {"matlab"}  # keyed, but the dataset has no such product
EOL_LATEST = {
    ("python", "3.11"): "3.11.11", ("python", "3.12"): "3.12.8", ("python", "3.13"): "3.13.1",
    ("node", "20"): "20.18.1", ("node", "22"): "22.12.0", ("postgres", "15"): "15.10",
    ("postgres", "16"): "16.6", ("django", "4.2"): "4.2.17", ("django", "5.2"): "5.2.1",
}  # fmt: skip

# What a repository is written in, by the technologies its component is built on.
LANGUAGE_OF = {
    "python": ["Python"], "django": ["Python", "HTML"], "node": ["TypeScript", "JavaScript"],
    "react": ["TypeScript", "CSS"], "angularjs": ["JavaScript", "HTML"], "java": ["Java"],
    "spring": ["Java"], "php": ["PHP"], "dotnet": ["C#"], "r": ["R"], "shiny": ["R", "CSS"],
    "matlab": ["MATLAB"], "nextflow": ["Nextflow"], "snakemake": ["Python"],
}  # fmt: skip
CODE_ORG = "bramblewood"
# A repository the connector's token was never given: every run reports it.
UNREADABLE = "Space Planning"

# Registered with the identity provider and on no record: (name, days before the build it was
# first seen). The last was dismissed by the architect.
UNRECORDED = [
    ("Room Booking", 9), ("Travel Requests", 9), ("Shared Lab Wiki", 9), ("Poster Printing", 6),
    ("Badge Photos", 3), ("Sequencing Core Orders", 2), ("Sign-in test (identity team)", 9),
]  # fmt: skip
DISMISSED = ("Sign-in test (identity team)", "A test registration the identity team keeps")

# name, capability keys (the first is where it is primary, if any), sourcing, unit, tier,
# users, maintainers, vendor, technologies [(tech, release)], health (good, fair, poor),
# and anything else that makes it what it is.
APPLICATIONS: list[tuple] = [
    ("Grant Management System", ["awards"], "saas", "SPO", "2", 420, 2, "granary", [], "good",
     {"purpose": "operations", "data_classes": ["financial", "personal"], "cost": 140000}),
    ("Research Ethics Portal", ["research_compliance"], "commercial", "CPO", "2", 900, 2, "dovetail",
     [("java", "11"), ("postgres", "13"), ("rhel", "8")], "fair",
     {"purpose": "operations", "data_classes": ["identifiable_research", "personal"], "cost": 85000, "regulated_record": True}),
    ("Conflict of Interest Disclosures", ["research_compliance"], "saas", "CPO", "3", 1600, 1, "dovetail", [], "good",
     {"purpose": "operations", "data_classes": ["personal"], "cost": 22000}),
    ("Clinical Trials Management", ["clinical_trials"], "commercial", "CLIN", "1", 310, 3, "ashgrove",
     [("java", "17"), ("postgres", "15"), ("rhel", "9")], "good",
     {"purpose": "mission", "data_classes": ["health", "identifiable_research"], "cost": 260000, "regulated_record": True, "research_continuity": True}),
    ("Electronic Health Record", ["clinical_record", "orders_results"], "saas", "CLINIC", "1", 640, 4, "medlark", [], "good",
     {"purpose": "mission", "data_classes": ["health", "payment_card"], "cost": 690000, "regulated_record": True}),
    ("Clinic Scheduler", ["patient_access"], "commercial", "PA", "2", 180, 1, "calendra",
     [("dotnet", "6"), ("winserver", "2012 R2")], "poor", {"purpose": "operations", "data_classes": ["health"], "cost": 48000, "story": "mismatch"}),
    ("Research Pharmacy Dispensing", ["pharmacy"], "commercial", "RPH", "1", 35, 2, "pillbox",
     [("dotnet", "8"), ("winserver", "2022")], "good", {"purpose": "mission", "data_classes": ["health"], "cost": 52000, "regulated_record": True}),
    ("Clinical Lab Information System", ["clinical_lab"], "commercial", "CLAB", "1", 60, 2, "helixware",
     [("java", "17"), ("postgres", "16"), ("rhel", "9")], "good", {"purpose": "mission", "data_classes": ["health"], "cost": 120000, "regulated_record": True}),
    ("Patient Portal", ["patient_communication"], "saas", "CLINIC", "2", 5200, 1, "medlark", [], "good",
     {"purpose": "operations", "data_classes": ["health"], "cost": 60000, "external_users": True}),
    ("Clinic Questionnaires", ["surveys"], "saas", "CLINIC", "3", 260, 1, "fieldnote", [], "fair",
     {"purpose": "operations", "data_classes": ["health"], "cost": 9000, "story": "clinic_surveys"}),
    ("Survey Hub", ["surveys"], "saas", "POPH", "2", 2100, 2, "fieldnote", [], "good",
     {"purpose": "mission", "data_classes": ["identifiable_research"], "cost": 38000, "story": "survey_primary"}),
    ("Old Surveys", ["surveys"], "built_here", "POPH", "4", 30, 1, None,
     [("php", "7.4"), ("mysql", "5.7"), ("ubuntu", "18.04")], "poor",
     {"purpose": "operations", "data_classes": ["identifiable_research"], "cost": 4000, "story": "survey_secondary"}),
    ("Specimen Tracker", ["biospecimens"], "built_here", "BIOR", "2", 380, 1, None,
     [("python", "3.9"), ("django", "3.2"), ("postgres", "13")], "fair", {"story": "worked_example"}),
    ("Freezer Watch", ["lab_data"], "built_here", "BIOR", "3", 45, 2, None,
     [("python", "3.12"), ("postgres", "15")], "good",
     {"purpose": "operations", "data_classes": ["internal"], "cost": 8000, "story": "freezer"}),
    ("Sequencing Run Manager", ["omics"], "commercial", "GEN", "2", 70, 2, "helixware",
     [("java", "17"), ("postgres", "13"), ("ubuntu", "22.04")], "good", {"purpose": "mission", "data_classes": ["deidentified_research"], "cost": 90000}),
    ("Genomics Pipeline", ["omics", "analysis"], "research_software", "GEN", "2", 140, 2, None,
     [("nextflow", "24"), ("python", "3.11"), ("kubernetes", "1.31")], "good", {"purpose": "mission", "data_classes": ["controlled_access"], "cost": 45000}),
    ("Imaging Data Server", ["instrument_data"], "open_source", "IMG", "2", 260, 2, "openmicro",
     [("java", "11"), ("postgres", "13"), ("ubuntu", "20.04")], "fair", {"purpose": "mission", "data_classes": ["deidentified_research"], "cost": 30000}),
    ("Flow Cytometry Scheduler", ["instrument_data"], "saas", "FLOW", "3", 190, 1, "calendra", [], "good",
     {"purpose": "operations", "data_classes": ["internal"], "cost": 6000}),
    ("Research Data Warehouse", ["research_data", "analysis"], "built_here", "ITRES", "2", 520, 3, None,
     [("python", "3.12"), ("postgres", "16"), ("kubernetes", "1.31")], "good",
     {"purpose": "insight", "data_classes": ["identifiable_research", "health"], "cost": 160000}),
    ("Cohort Analysis Platform", ["analysis"], "research_software", "COMP", "2", 220, 1, None,
     [("r", "4.3"), ("shiny", "1.8"), ("postgres", "13")], "fair",
     {"purpose": "mission", "data_classes": ["identifiable_research"], "cost": 25000, "story": "single_maintainer", "research_continuity": True}),
    ("High Performance Computing Portal", ["research_computing"], "open_source", "RC", "1", 860, 3, "biosuite",
     [("python", "3.11"), ("rhel", "8")], "good", {"purpose": "foundation", "data_classes": ["internal"], "cost": 310000}),
    ("Data Sharing Gateway", ["research_data"], "built_here", "RC", "2", 330, 2, None,
     [("node", "18"), ("postgres", "13"), ("ubuntu", "20.04")], "fair",
     {"purpose": "mission", "data_classes": ["controlled_access"], "cost": 40000, "external_users": True}),
    ("Electronic Lab Notebook Pilot", ["lab_data"], "saas", "COMP", "4", 40, 1, "meridian", [], "good",
     {"purpose": "mission", "lifecycle": "evaluating", "pace": "experimental", "data_classes": ["internal"], "cost": 5000, "story": "incubator"}),
    ("Lab Inventory", ["lab_data"], "saas", "SR", "3", 700, 1, "meridian", [], "good",
     {"purpose": "operations", "data_classes": ["internal"], "cost": 24000}),
    ("Participant Recruitment Registry", ["participants"], "built_here", "POPH", "2", 150, 2, None,
     [("java", "8"), ("tomcat", "8.5"), ("mysql", "5.7")], "poor",
     {"purpose": "mission", "data_classes": ["identifiable_research", "personal"], "cost": 35000}),
    ("eConsent", ["participants"], "saas", "CLIN", "2", 480, 1, "quillstone", [], "good",
     {"purpose": "mission", "data_classes": ["identifiable_research"], "cost": 30000, "external_users": True}),
    ("Study Protocol Library", ["study_management"], "low_code", "CLIN", "3", 260, 1, None, [], "fair",
     {"purpose": "operations", "data_classes": ["internal"], "cost": 3000}),
    ("Finance and Ledger", ["finance"], "saas", "FIN", "1", 210, 3, "ledgerline", [], "good",
     {"purpose": "operations", "data_classes": ["financial"], "cost": 450000, "regulated_record": True}),
    ("Expense Reports", ["finance"], "saas", "FIN", "3", 1900, 1, "ledgerline", [], "good",
     {"purpose": "operations", "data_classes": ["financial", "personal"], "cost": 26000}),
    ("Purchasing", ["procurement"], "saas", "FIN", "2", 600, 2, "tallyho", [], "good",
     {"purpose": "operations", "data_classes": ["financial"], "cost": 75000}),
    ("Human Resources and Payroll", ["people"], "saas", "HR", "1", 2050, 3, "staffbright", [], "good",
     {"purpose": "operations", "data_classes": ["personal", "financial"], "cost": 380000, "regulated_record": True}),
    ("Applicant Tracking", ["people"], "saas", "HR", "3", 120, 1, "staffbright", [], "fair",
     {"purpose": "operations", "data_classes": ["personal"], "cost": 18000}),
    ("Learning Management", ["learning"], "saas", "EDU", "2", 2000, 1, "pinecrest", [], "good",
     {"purpose": "operations", "data_classes": ["personal"], "cost": 55000}),
    ("Trainee Records", ["trainee_records"], "built_here", "EDU", "3", 40, 1, None,
     [("access", "2013")], "poor", {"purpose": "operations", "data_classes": ["personal"], "cost": 2000}),
    ("Facilities Work Orders", ["facilities"], "saas", "FAC", "3", 1400, 1, "brightdesk", [], "good",
     {"purpose": "operations", "data_classes": ["internal"], "cost": 21000}),
    ("Space Planning", ["facilities"], "built_here", "FAC", "4", 25, 1, None,
     [("php", "7.4"), ("mysql", "5.7")], "poor", {"purpose": "insight", "data_classes": ["internal"], "cost": 2500}),
    ("Public Website", ["communications"], "open_source", "COMMS", "2", 2000, 2, None,
     [("php", "8.3"), ("mysql", "8.0"), ("ubuntu", "22.04")], "good",
     {"purpose": "operations", "data_classes": ["public"], "cost": 32000, "sign_in": "none", "external_users": True}),
    ("Intranet", ["communications", "collaboration"], "saas", "COMMS", "3", 2000, 1, "kitewing", [], "good",
     {"purpose": "operations", "data_classes": ["internal"], "cost": 16000}),
    ("Donor Relations", ["philanthropy"], "saas", "PHIL", "2", 45, 1, "cinder", [], "good",
     {"purpose": "operations", "data_classes": ["personal", "financial"], "cost": 48000}),
    ("Event Registration", ["philanthropy", "communications"], "saas", "PHIL", "4", 30, 1, "fieldnote", [], "fair",
     {"purpose": "operations", "data_classes": ["personal", "payment_card"], "cost": 7000, "external_users": True}),
    ("Contracts Repository", ["legal"], "saas", "PRES", "2", 80, 1, "dovetail", [], "good",
     {"purpose": "operations", "data_classes": ["internal"], "cost": 19000}),
    ("Records Retention Archive", ["records"], "commercial", "CPO", "3", 60, 1, "dovetail",
     [("java", "11"), ("winserver", "2016")], "fair", {"purpose": "foundation", "data_classes": ["personal", "health"], "cost": 15000}),
    ("Identity and Sign-in", ["identity"], "saas", "ITINF", "1", 2100, 3, "keystone", [], "good",
     {"purpose": "foundation", "data_classes": ["personal"], "cost": 120000}),
    ("Email and Calendars", ["collaboration"], "saas", "ITINF", "1", 2100, 2, "kitewing", [], "good",
     {"purpose": "foundation", "data_classes": ["internal", "personal"], "cost": 210000}),
    ("Team Chat", ["collaboration"], "saas", "ITINF", "2", 1900, 1, "kitewing", [], "good",
     {"purpose": "foundation", "data_classes": ["internal"], "cost": 42000}),
    ("Service Desk", ["service_management"], "saas", "ITINF", "2", 2100, 2, "brightdesk", [], "good",
     {"purpose": "foundation", "data_classes": ["internal"], "cost": 64000}),
    ("Virtual Machine Platform", ["hosting"], "commercial", "ITINF", "1", 40, 3, "oakmere",
     [("rhel", "8")], "fair", {"purpose": "foundation", "data_classes": ["internal"], "cost": 230000}),
    ("Container Platform", ["hosting", "software_delivery"], "open_source", "ITINF", "2", 60, 2, None,
     [("kubernetes", "1.31"), ("ubuntu", "22.04")], "good", {"purpose": "foundation", "data_classes": ["internal"], "cost": 70000}),
    ("Security Monitoring", ["security"], "saas", "SEC", "1", 12, 2, "watchtower", [], "good",
     {"purpose": "foundation", "data_classes": ["personal", "internal"], "cost": 150000}),
    ("Application Monitoring", ["monitoring"], "saas", "ITINF", "2", 45, 2, "watchtower", [], "good",
     {"purpose": "foundation", "data_classes": ["internal"], "cost": 48000}),
    ("Code Repositories", ["software_delivery"], "saas", "ITINF", "2", 230, 2, None, [], "good",
     {"purpose": "foundation", "data_classes": ["internal"], "cost": 21000}),
    ("Integration Engine", ["integration"], "commercial", "ITAPP", "1", 15, 2, "larkfield",
     [("java", "11"), ("postgres", "13"), ("rhel", "8")], "fair",
     {"purpose": "foundation", "data_classes": ["health", "personal"], "cost": 95000}),
    ("Old Reports Server", ["analysis"], "commercial", "ITAPP", "3", 150, 1, "cobaltine",
     [("java", "8"), ("winserver", "2012 R2")], "poor", {"purpose": "insight", "data_classes": ["financial"], "cost": 30000, "story": "retired"}),
    ("Executive Dashboards", ["analysis"], "saas", "ITAPP", "3", 90, 1, "cinder", [], "good",
     {"purpose": "insight", "data_classes": ["financial"], "cost": 36000}),
    ("Biorepository Request Portal", ["study_management"], "low_code", "BIOR", "3", 210, 1, None, [], "fair",
     {"purpose": "operations", "data_classes": ["deidentified_research"], "cost": 4000}),
    ("Imaging Pipeline", ["instrument_data"], "research_software", "IMG", "3", 60, 2, None,
     [("python", "3.11"), ("snakemake", "8")], "good", {"story": "grant_ending"}),
]  # fmt: skip

# Research software that labs build and keep themselves: (kind of tool, capability, techs).
LAB_TOOLS = [
    ("Sample Tracker", "lab_data", [("python", "3.11"), ("postgres", "13")]),
    ("Image Analysis", "instrument_data", [("matlab", "R2019b")]),
    ("Analysis Pipeline", "analysis", [("r", "4.3"), ("snakemake", "8")]),
    ("Plate Reader Database", "lab_data", [("access", "2013")]),
    ("Variant Browser", "omics", [("python", "3.12"), ("react", "18"), ("postgres", "15")]),
    ("Cohort Dashboard", "analysis", [("r", "4.1"), ("shiny", "1.8")]),
    ("Mouse Colony Manager", "lab_data", [("php", "7.4"), ("mysql", "5.7")]),
]

# Applications that came in from the old spreadsheet and were never assessed.
UNASSESSED = [
    ("Visitor Badging", "facilities", "FAC"), ("Parking Permits", "facilities", "FAC"),
    ("Mailroom Tracking", "facilities", "FAC"), ("Print Management", "hosting", "ITINF"),
    ("Conference Room Booking", "facilities", "FAC"), ("Library Catalog", "research_data", "EDU"),
    ("Alumni Directory", "philanthropy", "PHIL"), ("Seminar Calendar", "communications", "COMMS"),
    ("Key Inventory", "facilities", "FAC"), ("Travel Booking", "finance", "FIN"),
    ("Poster Printing Queue", "communications", "COMMS"), ("Shuttle Schedule", "facilities", "FAC"),
]  # fmt: skip

# Data passing between applications: from, to, method, how often, the classes carried, and a
# name where "X to Y" would not say enough. Specimen Tracker sends only to applications that
# already depend on it, so the worked example keeps its three dependents.
INTERFACES = [
    ("Electronic Health Record", "Integration Engine", "messaging", "real_time", ["health"], "Clinical messages out"),
    ("Integration Engine", "Clinical Lab Information System", "messaging", "real_time", ["health"], "Orders to the lab"),
    ("Clinical Lab Information System", "Integration Engine", "messaging", "real_time", ["health"], "Results from the lab"),
    ("Integration Engine", "Research Pharmacy Dispensing", "messaging", "real_time", ["health"], "Orders to the pharmacy"),
    ("Integration Engine", "Clinical Trials Management", "messaging", "hourly", ["health"], "Visits and results to trials"),
    ("Electronic Health Record", "Patient Portal", "api", "real_time", ["health"], None),
    ("Clinic Scheduler", "Electronic Health Record", "manual", "daily", ["health"], "Appointments, re-keyed each morning"),
    ("Clinic Questionnaires", "Electronic Health Record", "file_transfer", "daily", ["health"], None),
    ("Clinical Trials Management", "Research Data Warehouse", "extract_load", "daily", ["identifiable_research"], "Trial data to the warehouse"),
    ("Specimen Tracker", "Research Data Warehouse", "extract_load", "daily", ["identifiable_research"], "Specimens to the warehouse"),
    ("Specimen Tracker", "Biorepository Request Portal", "api", "real_time", ["deidentified_research"], "What is available to request"),
    ("Specimen Tracker", "Freezer Watch", "api", "hourly", ["internal"], "Freezer positions"),
    ("Survey Hub", "Research Data Warehouse", "extract_load", "weekly", ["identifiable_research"], "Survey answers to the warehouse"),
    ("Research Data Warehouse", "Cohort Analysis Platform", "database_link", "on_demand", ["identifiable_research"], "Cohorts for analysis"),
    ("Research Data Warehouse", "Executive Dashboards", "extract_load", "daily", ["identifiable_research"], "Enrollment figures"),
    ("Research Data Warehouse", "Data Sharing Gateway", "manual", "on_demand", ["controlled_access"], "Approved data sets"),
    ("Sequencing Run Manager", "Genomics Pipeline", "file_transfer", "daily", ["controlled_access"], "Runs to the pipeline"),
    ("Participant Recruitment Registry", "eConsent", "api", "real_time", ["identifiable_research"], None),
    ("eConsent", "Clinical Trials Management", "api", "real_time", ["health"], "Signed consents"),
    ("Human Resources and Payroll", "Identity and Sign-in", "file_transfer", "daily", ["personal"], "Joiners and leavers"),
    ("Human Resources and Payroll", "Finance and Ledger", "extract_load", "monthly", ["financial"], "Payroll journal"),
    ("Human Resources and Payroll", "Learning Management", "file_transfer", "weekly", ["personal"], "Staff list"),
    ("Grant Management System", "Finance and Ledger", "api", "daily", ["financial"], "Awards and budgets"),
    ("Expense Reports", "Finance and Ledger", "extract_load", "weekly", ["financial"], None),
]  # fmt: skip

# What an application is for, in a sentence: by storyline, and by the kind of a lab's tool.
# Every other application says which unit uses it for what.
STORY_SUMMARIES = {
    "worked_example": "Tracks every biospecimen from collection to storage and release to a study.",
    "mismatch": "Books clinic appointments and rooms for research visits.",
    "clinic_surveys": "Questionnaires patients answer on a tablet before a clinic visit.",
    "survey_primary": "The institute's survey service: consent, participant surveys, and study data capture.",
    "survey_secondary": "An in-house survey tool from before the survey hub, still used by a few studies.",
    "freezer": "Watches freezer temperatures and pages whoever is on call when one drifts.",
    "single_maintainer": "Where cohort studies run their analyses, on a shared environment one engineer keeps.",
    "incubator": "A pilot of an electronic lab notebook with three labs.",
    "retired": "Reports for leadership, replaced by the executive dashboards.",
    "grant_ending": "Turns microscope images into measurements for the lab's imaging studies.",
}
LAB_SUMMARIES = {
    "Sample Tracker": "Where the lab records its samples, boxes, and freezer positions.",
    "Image Analysis": "Scripts that measure what the lab's microscope images show.",
    "Analysis Pipeline": "The lab's pipeline from raw sequencing data to results.",
    "Plate Reader Database": "Readings from the lab's plate reader, kept in a desktop database.",
    "Variant Browser": "A browser for the variants the lab has called across its samples.",
    "Cohort Dashboard": "Charts of the lab's cohort for its collaborators.",
    "Mouse Colony Manager": "Breeding, cages, and genotypes for the lab's mouse colony.",
}

WORKED_EXAMPLE = {
    "strategic_fit": 4, "functional_fit": 3, "future_need": 4, "reliability": 3,
    "maintainability": 2, "support_effort": 2, "change_effort": 2, "compliance": None,
}  # fmt: skip

RATIONALES = {
    "invest": ["It is central to the work and in good health; fund the next phase.",
               "Widely used and well run. Put more people on it."],
    "maintain": ["It does its job and costs little to keep. Keep it current.",
                 "Steady, and nobody wants it to change. Keep it as it is."],
    "tolerate": ["Little used, but harmless and cheap. Look again next year.",
                 "Not worth investing in, not worth the disruption of removing yet."],
    "modernize": ["Valuable, but on technology that is ageing. Upgrade it this year.",
                  "People rely on it; its platform is the problem. Re-platform it."],
    "replace": ["The need is real, the product is not. Find a successor.",
                "The vendor has stopped developing it. Plan the move."],
    "consolidate": ["It does what the primary already does. Move its users there."],
    "retire": ["Nobody needs it any more. Archive the data and switch it off."],
    "incubate": ["A pilot. Judge it on its success criteria at the end of the trial."],
    "assess": ["Too little is known to decide. Assess it first."],
}  # fmt: skip
