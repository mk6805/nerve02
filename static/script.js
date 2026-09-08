function getLocation() {

    navigator.geolocation.getCurrentPosition(

        function(position) {

            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            document.getElementById("result").innerHTML =
                `Latitude: ${latitude}<br>
                 Longitude: ${longitude}<br>
                 Getting location details...`;

            fetch("/api/location", {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    latitude: latitude,
                    longitude: longitude
                })

            })

            .then(response => response.json())

            .then(data => {

                console.log("Location saved:", data);

                if (data.error) {

                    document.getElementById("result").innerHTML =
                        `Error: ${data.error}`;

                    return;
                }

                // Store latest location in browser
                localStorage.setItem(
                    "userLocation",
                    JSON.stringify(data)
                );

                document.getElementById("result").innerHTML =
                    `Latitude: ${data.latitude}<br>
                     Longitude: ${data.longitude}<br>
                     Area: ${data.place_name || "Not available"}<br>
                     City: ${data.city || "Not available"}<br>
                     District: ${data.district || "Not available"}<br>
                     State: ${data.state || "Not available"}<br><br>
                     ✅ Location saved successfully.`;

            })

            .catch(error => {

                console.error(error);

                document.getElementById("result").innerHTML =
                    "Could not save location.";

            });
        },

        function(error) {

            document.getElementById("result").innerHTML =
                "Location permission denied.";

        }
    );
}


function showSavedLocation() {

    const savedLocation =
        localStorage.getItem("userLocation");

    if (!savedLocation) {
        return;
    }

    const data = JSON.parse(savedLocation);

    const latitude =
        document.getElementById("latitude");

    if (!latitude) {
        return;
    }

    document.getElementById("latitude").innerText =
        data.latitude;

    document.getElementById("longitude").innerText =
        data.longitude;

    document.getElementById("place_name").innerText =
        data.place_name || "Not available";

    document.getElementById("city").innerText =
        data.city || "Not available";

    document.getElementById("district").innerText =
        data.district || "Not available";

    document.getElementById("state").innerText =
        data.state || "Not available";
}


showSavedLocation();

function checkRisk() {

    const radius =
        Number(document.getElementById("radius").value);

    if (!radius || radius <= 0) {

        document.getElementById("riskResult").innerHTML =
            "Please enter a valid radius.";

        return;
    }

    const savedLocation =
        localStorage.getItem("userLocation");

    if (!savedLocation) {

        document.getElementById("riskResult").innerHTML =
            `No location found.<br>
             Please set your location first.`;

        return;
    }

    document.getElementById("riskResult").innerHTML =
        "Checking nearby disasters...";

    fetch("/api/check-risk", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            radius_km: radius
        })

    })

    .then(response => response.json())

    .then(data => {

        console.log("Risk result:", data);

        if (data.error) {

            document.getElementById("riskResult").innerHTML =
                `Error: ${data.error}`;

            return;
        }

        if (data.count === 0) {

            document.getElementById("riskResult").innerHTML =
                `✅ No disasters found within ${radius} km.`;

            return;
        }

        let html =
            `<h2>⚠️ Nearby Disasters</h2>`;

        data.disasters.forEach(
            function(disaster) {

                html += `
                    <div>

                        <b>${disaster.event_name || "Unnamed event"}</b>

                        <br>

                        Type:
                        ${disaster.disaster_type}

                        <br>

                        Distance:
                        ${disaster.distance_km} km

                        <br>

                        Magnitude:
                        ${disaster.magnitude ?? "N/A"}

                        <br>

                        Date:
                        ${disaster.event_date || "N/A"}

                    </div>

                    <hr>
                `;
            }
        );

        document.getElementById("riskResult").innerHTML =
            html;

    })

    .catch(error => {

        console.error(error);

        document.getElementById("riskResult").innerHTML =
            "Could not check disaster risk.";

    });
}