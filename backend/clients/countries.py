"""The countries a client can be in. The country picks the contract template (a contract has different clauses in different places)."""
COUNTRIES = [
    ("JO", "Jordan", "الأردن"), ("SA", "Saudi Arabia", "السعودية"), ("AE", "United Arab Emirates", "الإمارات"), ("KW", "Kuwait", "الكويت"),
    ("QA", "Qatar", "قطر"), ("BH", "Bahrain", "البحرين"), ("OM", "Oman", "عُمان"), ("EG", "Egypt", "مصر"), ("LB", "Lebanon", "لبنان"),
    ("IQ", "Iraq", "العراق"), ("PS", "Palestine", "فلسطين"), ("OTHER", "Other", "أخرى"),
]
CODES = [c[0] for c in COUNTRIES]
