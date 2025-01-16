let sessionToken = null; // To store the session token

// Function to handle login
async function login(email, password) {
  try {
    const formData = new FormData();
    formData.append("username", email);  // Replace 'email' with the username
    formData.append("password", password);

    const response = await fetch("http://127.0.0.1:8000/token", {
      method: "POST",
      body: formData,  // Send the credentials as form data
    });

    if (response.ok) {
      const data = await response.json();
      console.log("Login successful:", data);
      sessionToken = data.access_token;
      return data;
    } else {
      const error = await response.json();
      console.error("Login failed:", error.detail);
    }
  } catch (error) {
    console.error("Error during login:", error.message);
  }
}

// Function to handle WebSocket communication after login
function connectToWebSocket() {
  if (!sessionToken) {
    console.error("Cannot connect to WebSocket: No session token found.");
    return;
  }

  // Connect to the WebSocket server with session token as a query parameter
  const ws = new WebSocket(`ws://127.0.0.1:8000/ws?token=${sessionToken}`);

  ws.onopen = () => {
    console.log("Connected to WebSocket server!");
  };

  ws.onmessage = async (event) => {
    console.log(event)
    const message = JSON.parse(event.data);
    console.log("socket message", message)
    if (message.type = "new_volunteer_request") {
      const requestId = message.user_profile.email;
      console.log(`New volunteer request received: ${requestId}`);

      let decision = await getVolunteerDecision();
      decision = `new_volunteer_request:${decision ? "accept" : "reject"}` 
      ws.send(decision);
      console.log(`Response sent for request ${requestId}: ${decision}`);
    }
  };

  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
  };

  ws.onclose = () => {
    console.log("WebSocket connection closed");
  };
}

// Function to simulate a volunteer's decision
function getVolunteerDecision() {
  return new Promise((resolve) => {
    setTimeout(() => {
      const decision = Math.random() > 0.5; // Replace with actual decision logic
      resolve(decision);
    }, 2000); // Simulate a 2-second delay for decision-making
  });
}

// Main function to handle login and WebSocket connection
async function main() {
  const email = "v1@v.com"; // Replace with the user email
  const password = "string123"; // Replace with the user password

  const loggedIn = await login(email, password);

  if (loggedIn) {
    connectToWebSocket();
  } else {
    console.error("Login failed. Exiting...");
  }
}

// Run the main function
main();
