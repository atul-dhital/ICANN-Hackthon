$r1 = Invoke-WebRequest -Uri "http://127.0.0.1:8081/mail/" -Method Get -UseBasicParsing
$b1 = @{recipient="ram@example.np"; subject="Hello"; body="Visit https://-invalid-.example"} | ConvertTo-Json
$r2 = Invoke-WebRequest -Uri "http://127.0.0.1:8081/api/compose/validate" -Method Post -ContentType "application/json" -Body $b1 -UseBasicParsing
$b2 = @{recipient="राम@नेपाल.नेपाल"; subject="Hello"; body="Read https://example.com/docs"} | ConvertTo-Json
$r3 = Invoke-WebRequest -Uri "http://127.0.0.1:8081/api/compose/validate" -Method Post -ContentType "application/json" -Body ([System.Text.Encoding]::UTF8.GetBytes($b2)) -UseBasicParsing
Write-Host "R1:$($r1.StatusCode)"
Write-Host "R2:$($r2.StatusCode):$($r2.Content)"
Write-Host "R3:$($r3.StatusCode):$($r3.Content)"
