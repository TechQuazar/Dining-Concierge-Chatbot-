import json
import boto3

def lambda_handler(event, context):
    # TODO implement
    # Check if the incoming message is "hi"
    print('Event in LF0', event)
    
    if False and str(event['messages'][0]['unstructured']['text']).lower() == "hi":
        # You can add custom behavior for the "hi" message here
        text_response = "Hey! How can I assist you today?"
        
        response = {
            "messages": [
                {
                    "type": "unstructured",
                    "unstructured": {
                        "id": 1,
                        "text": text_response,
                    }
                }
            ]
        }
        return response
    
    else:
        # Initialize the Lex V2 client
        lexClient = boto3.client('lexv2-runtime')
        
        # Send the user's input to the Lex V2 bot
        lexResponse = lexClient.recognize_text(
            botId='5W2NQ8ELRB',         # Replace with your Lex V2 botId
            botAliasId='TSTALIASID',    # Replace with your Lex V2 botAliasId
            localeId='en_US',           # Replace with your bot's localeId
            sessionId='user1',          # Session ID (same as userId in Lex V1)
            text=event['messages'][0]['unstructured']['text']   # User input text
        )
        
        print('Lex Response obj', lexResponse)
        print("Session Attributes in LF0:", lexResponse.get("sessionState", {}).get("sessionAttributes", {}))
        
        # Extract the message from Lex V2 response
        lexMessage = lexResponse.get('messages', [])
        if lexMessage:
            text_response = lexMessage[0].get('content', 'No response from the bot.')
        else:
            text_response = 'No response from the bot.'

        # Construct the response to send back to the client
        response = {
            "messages": [
                {
                    "type": "unstructured",
                    "unstructured": {
                        "id": 1,
                        "text": text_response,
                    }
                }
            ]
        }
        return response

    # Default response in case no conditions are met
    response = {
        "messages": [
            {
                "type": "unstructured",
                "unstructured": {
                    "id": 1,
                    "text": "I'm still under development, please come back later!",
                }
            }
        ]
    }
    return response
