import json
import boto3
import logging
import datetime
from botocore.exceptions import ClientError

# Initialize the SQS client
sqs = boto3.client('sqs')
sqsQurl = "https://sqs.us-east-1.amazonaws.com/982081078287/DiningChatbotQueue"

def lambda_handler(event, context):
    # Extract intent from Lex event
    print('Received event:', event)
    intent_name = event['sessionState']['intent']['name']
    
    # Define handlers for different intents
    if intent_name == "GreetingIntent":
        return greeting_intent_handler()
    elif intent_name == "ThankYouIntent":
        return thank_you_intent_handler()
    elif intent_name == "DiningSuggestionsIntent":
        return dining_suggestions_intent_handler(event)
    else:
        raise Exception("Intent with name " + intent_name + " not supported")

def greeting_intent_handler():
    response_message = "Hi there, how can I assist you today?"
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Close"
            },
            "intent": {
                "confirmationState": "Confirmed",
                "name": "GreetingIntent",
                "state": "Fulfilled"
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": response_message
            }
        ]
    }

def thank_you_intent_handler():
    response_message = "You're welcome!"
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Close"
            },
            "intent": {
                "confirmationState": "Confirmed",
                "name": "ThankYouIntent",
                "state": "Fulfilled"
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": response_message
            }
        ]
    }

def dining_suggestions_intent_handler(event):
    print('Dining intent Event',event)
    event_slots = event['sessionState']['intent']['slots']
    source = event['invocationSource']
    
    if source == 'DialogCodeHook':

        # Validate slot values
        validated_result = validate_values(
             event_slots["Location"],
            event_slots["CuisineType"],
            event_slots['NoOfPeople'],
            event_slots['Date'],
            event_slots['Time'],
            event_slots['Email']
        )

        # If validation fails, prompt user to correct the invalid slot
        if not validated_result['valid_flag']:
            event_slots[validated_result['invalid_slot']] = None
            return elicit_slot(
                event['sessionState']['sessionAttributes'], 
                event['sessionState']['intent']['name'], 
                event_slots, 
                validated_result['invalid_slot'], 
                validated_result['message']
            )
        
    # Collect slot values
    slot_dict = {
        'Location': event_slots["Location"]['value']['interpretedValue'],
        'CuisineType': event_slots["CuisineType"]['value']['interpretedValue'],
        'NoOfPeople': event_slots['NoOfPeople']['value']['interpretedValue'],
        'Date': event_slots['Date']['value']['interpretedValue'],
        'Time': event_slots['Time']['value']['resolvedValues'][0],
        'Email': event_slots['Email']['value']['interpretedValue']
    }
    # Push validated data to SQS
    broadcast = push_to_sqs(sqsQurl, slot_dict)

    # Generate appropriate response based on SQS push success
    if broadcast:
        response_message = (
            "That's great! I have received your request for restaurant suggestions for "
            f"{event_slots['CuisineType']['value']['interpretedValue']} cuisine. You will shortly receive an email at "
            f"{event_slots['Email']['value']['interpretedValue']} with suggestions based on your preferences!"
        )
    else:
        response_message = "Sorry, something went wrong. Please try again later!"

    # Return the final response
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Close"
            },
            "intent": {
                "confirmationState": "Confirmed",
                "name": "DiningSuggestionsIntent",
                "state": "Fulfilled"
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": response_message
            }
        ]
    }

def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        "sessionState": {
            "dialogAction": {
                "type": "ElicitSlot",
                "slotToElicit": slot_to_elicit
            },
            "intent": {
                "name": intent_name,
                "slots": slots,
                "confirmationState": "None",
                "state": "InProgress"
            },
            "sessionAttributes": session_attributes
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": message["content"]
            }
        ]
    }

def push_to_sqs(QueueURL, msg_body):
    """
    Send message to SQS queue with the data from msg_body
    """
    print("Sending message to SQS queue...")
    
    try:
        # Send message to SQS queue
        response = sqs.send_message(
            QueueUrl=QueueURL,
            DelaySeconds=0,
            MessageAttributes={
                'Location': {
                    'DataType': 'String',
                    'StringValue': msg_body['Location']  
                },
                'CuisineType': {
                    'DataType': 'String',
                    'StringValue': msg_body['CuisineType']  
                },
                'NoOfPeople': {
                    'DataType': 'Number',
                    'StringValue': str(msg_body['NoOfPeople'])  
                },
                'Date': {
                    'DataType': 'String',
                    'StringValue': msg_body['Date']  
                },
                'Time': {
                    'DataType': 'String',
                    'StringValue': msg_body['Time']  
                },
                'Email': {
                    'DataType': 'String',
                    'StringValue': msg_body['Email']  
                }
            },
            MessageBody='Information about the diner'
        )
        print("Message sent successfully to SQS!")
        return response

    except ClientError as e:
        logging.error(f"Error sending message to SQS: {e}")
        return None    

def validate_values(loc, cuisine, people, date, time, email):
    # Define valid options for location, cuisine types, and number of people
    locations = ['manhattan', 'nyc', 'ny'] 
    cuisine_types = ['chinese', 'italian', 'mexican', 'japanese', 'american (new)', 'indian'] # "American (New)"
    no_of_people = [str(i) for i in range(1, 21)]
    no_ = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
           "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
           "eighteen", "nineteen", "twenty"]
    no_of_people.extend(no_)

    # Validate location
    if not loc:
        return ret_result(False, 'Location', "Where are you looking to eat?")
    elif loc['value']['interpretedValue'].lower() not in locations:
        return ret_result(False, 'Location', "Sorry, but we are currently serving only the New York City area!")

    # Validate cuisine type
    if not cuisine:
        return ret_result(False, 'CuisineType', "Great! What type of cuisine are you looking for?")
    elif cuisine['value']['interpretedValue'].lower() not in cuisine_types:
        return ret_result(False, 'CuisineType', "Currently available cuisine options are - " +
                          "[" + ", ".join(cuisine_types) + "]\nPlease choose one of these!")

    # Validate number of people
    if not people:
        return ret_result(False, 'NoOfPeople', "Got it, how many people will be there?")
    elif str(people['value']['interpretedValue']).lower() not in no_of_people:
        return ret_result(False, 'NoOfPeople', "We can accept bookings for up to 20 people only, please enter a valid number.")

    # Validate date
    if not date:
        return ret_result(False, 'Date', "Please tell me the date you're looking for restaurant suggestions.")
    try:
        booking_date = datetime.datetime.strptime(date['value']['interpretedValue'], '%Y-%m-%d').date()
        if booking_date < datetime.date.today():
            return ret_result(False, 'Date', "Oh snap! I can't book in the past as I don't have a time stone. You can look for suggestions for any date from today onwards.")
    except ValueError:
        return ret_result(False, 'Date', "Please provide a valid date in the format YYYY-MM-DD.")

    # Validate time
    if not time:
        return ret_result(False, 'Time', f"Ok, what time are you looking to dine out on {str(booking_date)}?")
    elif not date_time_validator(date['value']['interpretedValue'], time['value']['resolvedValues'][0]):
        return ret_result(False, 'Time', "Unfortunately, I'm not Dr. Strange, so I can't book for a time in the past. Please enter a time in the future!")

    # Validate email
    if not email:
        return ret_result(False, 'Email', "Perfect! Just type in your email address here so I can send the suggestions there.")
    elif '@' not in email['value']['interpretedValue'].lower():
        return ret_result(False, 'Email', "Please enter a valid email address.")

    # If all validations pass
    return ret_result(True, None, None)

def ret_result(valid_flag, invalid_slot, message):
    return {
        "valid_flag": valid_flag,
        "invalid_slot": invalid_slot,
        "message": {
            "contentType": "PlainText",
            "content": message
        }
    }    

def date_time_validator(date, time):
    """ 
    Validate that the time is not in the past based on the date.
    For now, we'll assume it's a simple validation to check if the time provided is not in the past today.
    """
    try:
        booking_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
        booking_time = datetime.datetime.strptime(time, '%H:%M').time()
        current_time = datetime.datetime.now().time()

        if booking_date == datetime.date.today() and booking_time < current_time:
            return False
        return True
    except ValueError:
        return False
