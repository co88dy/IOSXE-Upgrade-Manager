#!/bin/bash
curl -X POST -H "Content-Type: application/json" -d '{"ip_range": "10.10.20.181"}' http://localhost:5001/api/discover > discovery_response.txt 2>&1
echo "--- SERVER LOG ---" > discovery_log.txt
cat server.log >> discovery_log.txt
