
import json
import os
import firebase_admin
from firebase_admin import credentials, messaging, firestore
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Initialize Firebase Admin
# We use a singleton pattern to avoid re-initialization error
if not firebase_admin._apps:
    # In production (Render), we expect credentials in an environment variable
    # For local testing, we can use a path or skipped if not configured
    cred_json = os.environ.get('FIREBASE_ADMIN_JSON')
    if cred_json:
        try:
            # Defensive: Strip potentially added quotes from Render env var UI
            cred_json = cred_json.strip().strip("'").strip('"')
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("FIREBASE ADMIN: Initialized Successfully (Env Var)")
        except Exception as e:
            print(f"FIREBASE ADMIN ERROR: Failed to parse JSON. Error: {e}")
            print(f"JSON Preview: {cred_json[:20]}...") 
    else:
        # Fallback: Check for local file (for local development)
        # Assuming notifications.py is in accounts/, so root is one level up
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_path = os.path.join(base_dir, 'firebase_key.json')
        
        if os.path.exists(key_path):
             try:
                 cred = credentials.Certificate(key_path)
                 firebase_admin.initialize_app(cred)
                 print(f"FIREBASE ADMIN: Initialized Successfully (Local File: {key_path})")
             except Exception as e:
                 print(f"FIREBASE ADMIN LOCAL FILE ERROR: {e}")
        else:
             print("WARNING: FIREBASE_ADMIN_JSON not found AND firebase_key.json not found. Notifications will fail.")

@csrf_exempt
def send_notification(request):
    # Health Check (GET) - Verify Firebase Init
    if request.method == 'GET':
        status = "Initialized" if firebase_admin._apps else "Not Initialized"
        return JsonResponse({'firebase_status': status})

    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    try:
        print(f"Notification Request: {request.body.decode('utf-8')}")
        data = json.loads(request.body)
        receiver_id = data.get('receiver_id')
        title = data.get('title', 'New Message')
        body = data.get('body', 'You have a new message')
        
        if not receiver_id:
             return JsonResponse({'error': 'receiver_id required'}, status=400)

        # 1. Get FCM Token from Firestore
        # Note: This assumes utilizing the same project credentials for both Auth and Firestore
        db = firestore.client()
        user_doc = db.collection('users').document(receiver_id).get()
        
        if not user_doc.exists:
             return JsonResponse({'error': 'User not found'}, status=404)
             
        user_data = user_doc.to_dict()
        fcm_token = user_data.get('fcm_token')
        
        if not fcm_token:
             return JsonResponse({'error': 'User has no FCM token'}, status=404)

        # 2. Send Message
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data={
                'click_action': 'FLUTTER_NOTIFICATION_CLICK',
                'receiver_id': receiver_id,
            },
            token=fcm_token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                     channel_id='high_importance_channel',
                     default_sound=True,
                ),
            ),
        )

        response = messaging.send(message)
        return JsonResponse({'status': 'sent', 'message_id': response})

    except Exception as e:
        print(f"Notification Error: {e}")
        return JsonResponse({'error': str(e)}, status=500)
