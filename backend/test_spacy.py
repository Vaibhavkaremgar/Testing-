"""
Diagnostic script to check if spaCy is working
"""

print("=" * 60)
print("SPACY DIAGNOSTIC CHECK")
print("=" * 60)

# Test 1: Check if spaCy is installed
print("\n1. Checking if spaCy is installed...")
try:
    import spacy
    print("   ✅ spaCy is installed (version: {})".format(spacy.__version__))
except ImportError:
    print("   ❌ spaCy is NOT installed")
    print("   Run: pip install spacy==3.7.2")
    exit(1)

# Test 2: Check if model is downloaded
print("\n2. Checking if en_core_web_sm model is available...")
try:
    nlp = spacy.load("en_core_web_sm")
    print("   ✅ Model loaded successfully")
except OSError:
    print("   ❌ Model NOT found")
    print("   Run: python -m spacy download en_core_web_sm")
    exit(1)

# Test 3: Test NLP processing
print("\n3. Testing NLP processing...")
test_text = "Developed APIs using Python. Reduced latency by 40%. Led team of 3 developers."
doc = nlp(test_text)

verbs = [token.lemma_ for token in doc if token.pos_ == "VERB"]
entities = [(ent.text, ent.label_) for ent in doc.ents]

print(f"   Text: {test_text}")
print(f"   Verbs found: {verbs}")
print(f"   Entities found: {entities}")

if verbs and entities:
    print("   ✅ NLP processing works correctly")
else:
    print("   ⚠️  NLP processing may have issues")

# Test 4: Test get_nlp_signals function
print("\n4. Testing get_nlp_signals function...")
try:
    from app.spacy_nlp import get_nlp_signals, SPACY_AVAILABLE
    
    print(f"   SPACY_AVAILABLE: {SPACY_AVAILABLE}")
    
    if SPACY_AVAILABLE:
        signals = get_nlp_signals(test_text)
        print(f"   Action verb count: {signals['action_verb_count']}")
        print(f"   Verb density: {signals['verb_density']}")
        print(f"   Impact count: {signals['impact_count']}")
        print(f"   Leadership count: {signals['leadership_count']}")
        
        if signals['action_verb_count'] > 0:
            print("   ✅ get_nlp_signals works correctly")
        else:
            print("   ⚠️  No action verbs detected")
    else:
        print("   ❌ SPACY_AVAILABLE is False")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 5: Test balanced scoring
print("\n5. Testing balanced scoring...")
try:
    from app.balanced_scoring import evaluate_resume_balanced
    
    resume_data = {
        'full_text': """
        Software Engineer with 3 years experience.
        Developed RESTful APIs using Python and Flask.
        Implemented caching layer, reducing response time by 40%.
        Led team of 3 developers on microservices migration.
        Collaborated with cross-functional teams.
        """,
        'years_of_experience': 3
    }
    
    job_requirements = {
        'required_skills': ['Python', 'Flask', 'API'],
        'experience_min': 2,
        'experience_max': 5,
        'description': 'Backend developer'
    }
    
    result = evaluate_resume_balanced(resume_data, job_requirements)
    
    print(f"   Total Score: {result['total_score']}/100")
    print(f"   Experience: {result['components']['experience']['score']}/35")
    print(f"   Skills: {result['components']['skills']['score']}/30")
    print(f"   Projects: {result['components']['projects']['score']}/20")
    print(f"   Education: {result['components']['education']['score']}/10")
    print(f"   Soft Skills: {result['components']['soft_skills']['score']}/5")
    
    if result['total_score'] >= 70:
        print("   ✅ Scoring works correctly (score >= 70)")
    elif result['total_score'] >= 50:
        print("   ⚠️  Score is moderate (50-70). spaCy may not be working.")
    else:
        print("   ❌ Score is too low (<50). spaCy is likely not working.")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
