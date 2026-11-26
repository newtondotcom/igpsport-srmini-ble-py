search in the app where the srmini sofware is fetched from and how it is updated

repair path :
POST https://prod.en.igpsport.com/service/mobile/api/Device/UpdateRepairTool
(CN: https://prod.zh.igpsport.com ; older enapi/appapi hosts are dead/unreachable)

Auth required (unauthenticated call → HTTP 401 www-authenticate: Bearer):
- Authorization: <Ride accessToken>
- plus app request-signing headers (IgpNetSignHelper / NativeCrypto)

Body from this device:
{
  "devName": "SR mini",
  "manufactureData": "00_30_00_00_00_00_00_8d_73_00_01_00_00_00_00_00_00_00_00_00",
  "deviceId": null
}

Response data.firmwareUrl is the repair download link (app saves as "<deviceName>_update.zip");
also returns deviceName, dfuImage, firmwareType.

Related (also auth-gated): GET /service/mobile/api/Device/GetFirmwareUpdate
  ?ManufactureData=...&Name=SR%20mini

set custom light mode

# radar detection
Blind NUS sequence to enable radar detection
Blind radar detection events parsing
Compare to acquisition made on real data


