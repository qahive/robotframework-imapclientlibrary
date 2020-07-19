*** settings ***
Library    IMAPClientLibrary
Library    OperatingSystem


*** Test Cases ***
Get email and otp message
    Init email client    %{IMAP_HOST}    %{IMAP_EMAIL}    %{IMAP_PASSWORD}
    ${email} =    Wait for email      sender=atthaboon@gmail.com
    Log    ${email.body}
