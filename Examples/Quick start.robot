*** settings ***
Library    IMAPClientLibrary


*** Test Cases ***
Get email and otp message
    ${IMAP_HOST} =    Get Variable Value    ${IMAP_HOST}
    ${IMAP_EMAIL} =    Get Variable Value    ${IMAP_EMAIL}
    ${IMAP_PASSWORD} =    Get Variable Value    ${IMAP_PASSWORD}
    Init email client    ${IMAP_HOST}    ${IMAP_EMAIL}    ${IMAP_PASSWORD}
    # Wait For Email    
