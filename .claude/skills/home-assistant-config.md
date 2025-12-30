---
name: home-assistant-config
description: Configuration and connection details for the user's Home Assistant instance
---

# Home Assistant Configuration

## Production URL
The user's Home Assistant installation is accessible at:

**https://home.danielshaprvt.work/**

**IMPORTANT:** Always use this URL when accessing Home Assistant. Do NOT use:
- http://homeassistant.local:8123
- http://localhost:8123
- Any other URL

This is the production instance that should be used for all testing, configuration, and integration work.

## Integration Testing
When testing the Israel Transportation integration:
1. Navigate to https://home.danielshaprvt.work/
2. Access HACS from the sidebar
3. Find "Israel Transportation" integration
4. Test all transport types (bus, train, light rail)

## Important Notes
- This URL has been mentioned multiple times in conversations
- Always remember to use the correct URL to avoid wasting time
- The integration is distributed via HACS from the public repository
- **CRITICAL:** Home Assistant automatically reloads custom components when downloaded via HACS - NO RESTART NEEDED after downloading from HACS
