# Homeserver Cloud Watchdog

24/7 autonomous cloud watchdog for automatic resurrection of home server via Wake-on-LAN over Internet.

## How it works:
1. Runs automatically via GitHub Actions every 10 minutes.
2. Checks if apartment router is reachable (Port 80).
3. Checks if homeserver is reachable (Port 2222).
4. If router is UP but homeserver is DOWN -> power restored after outage, but server is off.
5. Sends Wake-on-LAN Magic Packet to wake up the server.
