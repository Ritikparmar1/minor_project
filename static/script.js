function sendMessage() {

    let input = document.getElementById("question");

    let question = input.value.trim();

    if (question === "") {
        return;
    }


    // Show user message

    addUserMessage(question);


    // Clear input

    input.value = "";


    // Send question to Python Flask

    fetch("/chat", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            question: question
        })

    })

    .then(response => response.json())

    .then(data => {

        addBotMessage(data.answer);

    })

    .catch(error => {

        console.log(error);

        addBotMessage(
            "❌ Sorry, something went wrong with the server."
        );

    });
}


function askQuestion(question) {

    document.getElementById("question").value = question;

    sendMessage();
}


function handleEnter(event) {

    if (event.key === "Enter") {

        sendMessage();

    }

}


function addUserMessage(message) {

    let chatBox = document.getElementById("chat-box");

    let messageDiv = document.createElement("div");

    messageDiv.className = "user-message";

    messageDiv.innerText = message;

    chatBox.appendChild(messageDiv);

    chatBox.scrollTop = chatBox.scrollHeight;
}


function addBotMessage(message) {

    let chatBox = document.getElementById("chat-box");

    let messageDiv = document.createElement("div");

    messageDiv.className = "bot-message";

    messageDiv.innerHTML = message;

    chatBox.appendChild(messageDiv);

    chatBox.scrollTop = chatBox.scrollHeight;
}