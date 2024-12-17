import { SQSClient, ReceiveMessageCommand, DeleteMessageCommand } from "@aws-sdk/client-sqs";
import { Client } from '@opensearch-project/opensearch';
import { DynamoDBClient, GetItemCommand, ScanCommand, DescribeTableCommand, QueryCommand } from "@aws-sdk/client-dynamodb";
import { SESClient, SendEmailCommand } from "@aws-sdk/client-ses";

// SQS queue URL
const queueUrl = "***********";

// OpenSearch index credentials
const openSearchUrl = "https://search-restaurant-search-t7nrqqo6o44fno3rjfc7a47qhe.us-east-1.es.amazonaws.com";
const openSearchUsername = "***********";
const openSearchPassword = "***********";
const indexName = "restaurants";

// DynamoDB table name
const TABLE_NAME = 'yelp-restaurants';

// AWS Client initialization
const sqsClient = new SQSClient({ region: "us-east-1" });
const opensearchClient = new Client({
  node: openSearchUrl,
  auth: { username: openSearchUsername, password: openSearchPassword },
  ssl: { rejectUnauthorized: false }
});
const dynamoDBClient = new DynamoDBClient({
  region: 'us-east-1',
  credentials: {
    accessKeyId: '***********',
    secretAccessKey: '***********',
  }
});
const sesClient = new SESClient({
  region: 'us-east-1',
  credentials: {
    accessKeyId: '***********',
    secretAccessKey: '***********',
  }
});

// Convert all DynamoDB values to strings
function convertToString(value) {
  if (!value) return 'N/A';
  if (value.S) return value.S;
  if (value.N) return value.N.toString();
  if (value.M) return JSON.stringify(value.M); // Handle nested objects
  return String(value); // Fallback for other types
}

function createEmailBody(restaurants, members, diningTime) {
  console.log("------createEmailBody1-------");
  console.log("Extracted DiningTime:", diningTime);
  console.log("Extracted Members:", members);
  console.log("------createEmailBody2-------");
  
  let emailBody = `Here is a list of restaurants for ${members} people at ${diningTime} today!:\n\n`;
  
  
  restaurants.forEach((restaurant, index) => {
    emailBody += formatRestaurantDetails(restaurant) + "\n\n"; // Add a blank line between restaurants
  });
  return emailBody;
}

function formatRestaurantDetails(restaurant) {
  const {
    //businessId: { S: businessId },
    name: { S: name },
    address: { S: address },
    rating: { N: rating },
    num_reviews: { N:review_count }
  } = restaurant;

  // Format the restaurant details into a user-friendly message
  const formattedMessage = `
    Restaurant ${name} has a rating of ${rating} and (${review_count} reviews). \n It is located at ${address}`;

  return formattedMessage.trim();
}

async function sendEmail(recipientEmail, emailBody) {
    const params = {
        Destination: {
            ToAddresses: [recipientEmail], // Recipient email
        },
        Message: {
            Body: {
                Text: { Data: emailBody },
            },
            Subject: { Data: "Your Dining Recommendations" }, // Email subject
        },
        // Sender and Recipient is the same
        Source: [recipientEmail], // Replace with a verified SES email address
    };

    try {
        const data = await sesClient.send(new SendEmailCommand(params));
        console.log("Email sent! Message ID: ", data.MessageId);
    } catch (error) {
        console.error("Error sending email: ", error);
    }
}




// Lambda handler
export const handler = async (event) => {
  try {

    const receiveMessageParams = {
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 1,
      WaitTimeSeconds: 20,
      MessageAttributeNames: ["All"],
      AttributeNames: ["All"]
    };

    console.log('Polling SQS for messages...');
    const data = await sqsClient.send(new ReceiveMessageCommand(receiveMessageParams));
    // console.log('data',data)
    if (data.Messages && data.Messages.length > 0) {
      const message = data.Messages[0];
      const messageBody = message.MessageAttributes;
      const CuisineType = messageBody.CuisineType.StringValue;
      const Date = messageBody.Date.StringValue;
      const Email = messageBody.Email.StringValue;
      const NoOfPeople = messageBody.NoOfPeople.StringValue;
      const Time = messageBody.Time.StringValue;

      const formattedCuisine = CuisineType.charAt(0).toUpperCase() + CuisineType.slice(1).toLowerCase();
      console.log(`Searching OpenSearch for cuisine: ${formattedCuisine}`);

      const query = {
  index: indexName,
  body: { query: { match: { "Cuisine": formattedCuisine } } }
};

try {
  const openSearchResponse = await opensearchClient.search(query);
  console.log('OpenSearch Response:', JSON.stringify(openSearchResponse.body.hits.hits, null, 2));

  const restaurantIds = openSearchResponse.body.hits.hits.map(hit => hit._source.RestaurantID);
  const restaurantDets = await Promise.all(
    restaurantIds.map(async (businessId) => {
      const queryParams = {
        TableName: TABLE_NAME,
        Key: { "business_id": { S: businessId } }
      };

      try {
        const response = await dynamoDBClient.send(new GetItemCommand(queryParams));
        return response.Item || null;
      } catch (error) {
        console.error(`Error fetching item for business_id: ${businessId}`, error);
        return null;
      }
    })
  );

  const validRestaurants = restaurantDets.filter(item => item !== null);
  if (validRestaurants.length === 0) {
    console.log('No valid restaurant details found.');
    return;
  }

  const emailBody = createEmailBody(validRestaurants, NoOfPeople, Time);
  await sendEmail(Email, emailBody);

  const deleteParams = { QueueUrl: queueUrl, ReceiptHandle: message.ReceiptHandle };
  await sqsClient.send(new DeleteMessageCommand(deleteParams));
  console.log('Message deleted successfully from SQS.');

} catch (error) {
  console.error('Error searching OpenSearch or querying DynamoDB:', error);
}
}
}catch(error)
{
    console.error('Error searching OpenSearch or querying DynamoDB:', error);

}
};

//       const openSearchResponse = await opensearchClient.search(query);
//       console.log('OpenSearch Response:', JSON.stringify(openSearchResponse.body.hits.hits, null, 2));

//       const restaurantIds = openSearchResponse.body.hits.hits.map(hit => hit._source.RestaurantID);
//       // const res = await scanTable()
//       // console.log('RES',res)

//       const restaurantDets = await Promise.all(
//         restaurantIds.map(async (businessId) => {
//           // const getItemParams = { TableName: TABLE_NAME, Key: { business_id: { S: business_id } } };
//           console.log("Business ID:",businessId)
//           const queryParams = {
//                 TableName: TABLE_NAME,
//                 Key:{
//                   "business_id":{S:businessId}
//                 }

//             };
//             console.log('Query Params',queryParams)
//           // console.log('Fetching restaurant details with params:', JSON.stringify(getItemParams, null, 2));

//           try {
//             // const response = await dynamoDBClient.send(new GetItemCommand(getItemParams));
//             const response = await dynamoDBClient.send(new GetItemCommand(queryParams));
//             console.log("Query Response:", response);
//             // console.log('DynamoDB Response:', JSON.stringify(response, null, 2));
//             return response.Item || null;
//           } catch (error) {
//             console.error(`Error fetching item for business_id: ${businessId}`, error);
//             return null;
//           }
//         })
//       );

//       const validRestaurants = restaurantDets.filter(item => item !== null);
//       if (validRestaurants.length === 0) {
//         console.log('No valid restaurant details found.');
//         return;
//       }

//       const emailBody = createEmailBody(validRestaurants, NoOfPeople, Time);
//       await sendEmail(Email, emailBody);

//       const deleteParams = { QueueUrl: queueUrl, ReceiptHandle: message.ReceiptHandle };
//       await sqsClient.send(new DeleteMessageCommand(deleteParams));
//       console.log('Message deleted successfully from SQS.');
//     } else {
//       console.log('No messages in the queue.');
//     }
//   } catch (error) {
//     console.error('Error processing message:', error);
//   }
// };
