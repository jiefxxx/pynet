var exampleSocket = new WebSocket("ws://127.0.0.1:8080/");
exampleSocket.onopen = function (event) {
  exampleSocket.send("Voici un texte que le serveur attend de recevoir dès que possible !");
}
exampleSocket.onmessage = function (event) {
  console.log(event.data);
}