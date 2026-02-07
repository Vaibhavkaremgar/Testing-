import sqlite3

def check_candidate(name):
    conn = sqlite3.connect('talentai.db')
    cursor = conn.cursor()
    
    try:
        # Search for candidate by name
        cursor.execute("SELECT id, name, email, phone, resume_text FROM candidates WHERE name LIKE ?", (f"%{name}%",))
        results = cursor.fetchall()
        
        if results:
            print(f"Found {len(results)} candidate(s) matching '{name}':")
            for candidate in results:
                print(f"  ID: {candidate[0]}")
                print(f"  Name: {candidate[1]}")
                print(f"  Email: {candidate[2]}")
                print(f"  Phone: {candidate[3]}")
                print(f"  Has Resume Text: {'Yes' if candidate[4] else 'No'}")
                print("-" * 40)
        else:
            print(f"No candidates found matching '{name}'")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_candidate("John Smith")