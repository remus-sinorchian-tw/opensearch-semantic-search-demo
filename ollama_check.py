import ollama
import sys

# --- Configuration ---
# The client defaults to http://127.0.0.1:11434. 
# We only pass 'host' if it's different (e.g., running in Docker or remote).
# To check the default connection, we can instantiate it without arguments.
try:
    client = ollama.Client()

    # --- Connection Check ---
    # The list() method is a simple way to confirm the server is reachable.
    print("✅ Attempting to connect to local Ollama service...")
    
    # This will raise an exception if the service is not running
    models = client.list() 
    
    print("\n----------------------------------------------------")
    print("🎉 SUCCESS: Connection established to Ollama service.")
    print("----------------------------------------------------")

    if not models.get('models'):
        print("⚠️ Warning: Ollama is running, but no models are currently downloaded.")
        print("   Use 'ollama pull <model_name>' to download one (e.g., 'ollama pull llama3').")
    else:
        print("Currently available models:")
        for model in models['models']:
            print(f"   - {model['model']} (Size: {round(model['size'] / (1024**3), 2)} GB)")

except ConnectionRefusedError:
    print("\n❌ ERROR: Connection Refused.")
    print("   Please ensure the Ollama application is running on your machine.")
    sys.exit(1)
except ollama.RequestError as e:
    # This catches errors like the 404/500 if the model isn't found or server crashes
    print(f"\n❌ ERROR: An Ollama request error occurred. Details: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ ERROR: An unexpected error occurred: {e}")
    sys.exit(1)