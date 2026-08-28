function getLocation() {

    navigator.geolocation.getCurrentPosition(
        function(position) {

            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            document.getElementById("result").innerHTML =
                `Latitude: ${latitude}<br>
                 Longitude: ${longitude}`;

            fetch("/api/location", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    latitude: latitude,
                    longitude: longitude
                })
            });
        },

        function(error) {
            document.getElementById("result").innerHTML =
                "Location permission denied.";
        }
    );
}