import google.generativeai as genai
import os

# Use the key hardcoded in app.py to test it
API_KEY = 'AIzaSyDhj5eznHfo9Dt80Ptvm_pi-LVqd_2i8oc'
genai.configure(api_key=API_KEY)

print(f"Testing Gemini API with key: {API_KEY[:5]}...")

try:
    # Test 1: Simple Generation
    print("Test 1: Simple Generation")
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content("Hello, can you hear me?")
    print(f"Success! Response: {response.text}")
    
    # Test 2: File Upload (Simulate audio upload with a text file as dummy or small wav if possible)
    # We'll create a dummy file
    print("\nTest 2: File Upload")
    with open("test.txt", "w") as f:
        f.write("This is a test file.")
        
    myfile = genai.upload_file("test.txt")
    print(f"Upload successful. URI: {myfile.uri}")
    
    # Clean up
    genai.delete_file(myfile.name)
    print("File deleted.")
    
except Exception as e:
    print(f"\nERROR: {e}")
