"""
Email service for My Story Buddy
Handles OTP delivery and other email notifications
"""
import os
import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class EmailService:
    """Email service for sending OTP and notifications"""
    
    def __init__(self):
        self.ses_client = None
        self.smtp_config = None
        self._initialize_email_service()
    
    def _initialize_email_service(self):
        """Initialize email service (SES or SMTP)"""
        try:
            # Try to initialize AWS SES first
            self.ses_client = boto3.client(
                'ses',
                region_name=os.getenv('AWS_REGION', 'us-west-2')
            )
            logger.info("AWS SES client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize AWS SES: {str(e)}")
            
            # Fallback to SMTP configuration
            self.smtp_config = {
                'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                'smtp_port': int(os.getenv('SMTP_PORT', '587')),
                'smtp_username': os.getenv('SMTP_USERNAME'),
                'smtp_password': os.getenv('SMTP_PASSWORD'),
                'from_email': os.getenv('FROM_EMAIL', 'noreply@mystorybuddy.com')
            }
            
            if self.smtp_config['smtp_username'] and self.smtp_config['smtp_password']:
                logger.info("SMTP configuration loaded successfully")
            else:
                logger.warning("No email service configured. OTP emails will be logged only.")
    
    async def send_otp_email(self, email: str, otp: str, first_name: Optional[str] = None) -> bool:
        """Send OTP email to user"""
        try:
            subject = "Your My Story Buddy Login Code"
            
            # Create HTML email content
            html_content = self._create_otp_email_html(otp, first_name)
            text_content = self._create_otp_email_text(otp, first_name)
            
            success = await self._send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
            if success:
                logger.info(f"OTP email sent successfully to {email}")
            else:
                logger.error(f"Failed to send OTP email to {email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending OTP email to {email}: {str(e)}")
            return False
    
    async def send_welcome_email(self, email: str, first_name: str) -> bool:
        """Send welcome email to new user"""
        try:
            subject = "Welcome to My Story Buddy! 🎉"
            
            html_content = self._create_welcome_email_html(first_name)
            text_content = self._create_welcome_email_text(first_name)
            
            success = await self._send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
            if success:
                logger.info(f"Welcome email sent successfully to {email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending welcome email to {email}: {str(e)}")
            return False
    
    async def _send_email(self, to_email: str, subject: str, 
                         html_content: str, text_content: str) -> bool:
        """Send email using available service (SES or SMTP)"""
        
        # Try AWS SES first
        if self.ses_client:
            return await self._send_via_ses(to_email, subject, html_content, text_content)
        
        # Fallback to SMTP
        elif self.smtp_config and self.smtp_config['smtp_username']:
            return await self._send_via_smtp(to_email, subject, html_content, text_content)
        
        # If no email service is configured, log the email content
        else:
            logger.warning("No email service configured. Email content:")
            logger.warning(f"To: {to_email}")
            logger.warning(f"Subject: {subject}")
            logger.warning(f"Content: {text_content}")
            return True  # Return True for development purposes
    
    async def _send_via_ses(self, to_email: str, subject: str, 
                           html_content: str, text_content: str) -> bool:
        """Send email via AWS SES"""
        try:
            from_email = os.getenv('FROM_EMAIL', 'noreply@mystorybuddy.com')
            
            response = self.ses_client.send_email(
                Source=from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': text_content, 'Charset': 'UTF-8'},
                        'Html': {'Data': html_content, 'Charset': 'UTF-8'}
                    }
                }
            )
            
            logger.info(f"Email sent via SES. MessageId: {response['MessageId']}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"SES error ({error_code}): {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending via SES: {str(e)}")
            return False
    
    async def _send_via_smtp(self, to_email: str, subject: str, 
                            html_content: str, text_content: str) -> bool:
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_config['from_email']
            msg['To'] = to_email
            
            # Add text and HTML parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_config['smtp_server'], self.smtp_config['smtp_port']) as server:
                server.starttls()
                server.login(self.smtp_config['smtp_username'], self.smtp_config['smtp_password'])
                server.send_message(msg)
            
            logger.info(f"Email sent via SMTP to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"SMTP error: {str(e)}")
            return False
    
    def _create_otp_email_html(self, otp: str, first_name: Optional[str] = None) -> str:
        """Create HTML content for OTP email"""
        name = first_name if first_name else "there"
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Your My Story Buddy Login Code</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; background-color: #f8f9fa;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #E8E3FF, #DDD4FF); padding: 40px 30px; text-align: center;">
                    <h1 style="margin: 0; color: #1a1a1a; font-size: 28px; font-weight: 700;">My Story Buddy</h1>
                    <p style="margin: 8px 0 0 0; color: #666; font-size: 16px;">Your magical storytelling companion</p>
                </div>
                
                <!-- Content -->
                <div style="padding: 40px 30px;">
                    <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 24px; font-weight: 600;">Hi {name}! 👋</h2>
                    
                    <p style="margin: 0 0 30px 0; color: #666; font-size: 16px; line-height: 1.6;">
                        Here's your login code for My Story Buddy. Enter this code to access your account and continue creating magical stories!
                    </p>
                    
                    <!-- OTP Code -->
                    <div style="text-align: center; margin: 40px 0;">
                        <div style="display: inline-block; background: #f8f9fa; border: 2px solid #E8E3FF; border-radius: 12px; padding: 20px 40px;">
                            <div style="font-size: 36px; font-weight: 700; color: #1a1a1a; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                                {otp}
                            </div>
                        </div>
                    </div>
                    
                    <p style="margin: 30px 0 0 0; color: #666; font-size: 14px; line-height: 1.6;">
                        <strong>Important:</strong> This code will expire in 5 minutes for your security. If you didn't request this code, please ignore this email.
                    </p>
                </div>
                
                <!-- Footer -->
                <div style="background: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #f0f0f0;">
                    <p style="margin: 0; color: #999; font-size: 14px;">
                        Happy storytelling! 📚✨<br>
                        The My Story Buddy Team
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_otp_email_text(self, otp: str, first_name: Optional[str] = None) -> str:
        """Create text content for OTP email"""
        name = first_name if first_name else "there"
        
        return f"""
        Hi {name}!

        Here's your login code for My Story Buddy:

        {otp}

        Enter this code to access your account and continue creating magical stories!

        Important: This code will expire in 5 minutes for your security.
        If you didn't request this code, please ignore this email.

        Happy storytelling! 📚✨
        The My Story Buddy Team
        """
    
    def _create_welcome_email_html(self, first_name: str) -> str:
        """Create HTML content for welcome email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Welcome to My Story Buddy!</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; background-color: #f8f9fa;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #E8E3FF, #DDD4FF); padding: 40px 30px; text-align: center;">
                    <h1 style="margin: 0; color: #1a1a1a; font-size: 28px; font-weight: 700;">Welcome to My Story Buddy! 🎉</h1>
                </div>
                
                <!-- Content -->
                <div style="padding: 40px 30px;">
                    <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 24px; font-weight: 600;">Hi {first_name}! 👋</h2>
                    
                    <p style="margin: 0 0 20px 0; color: #666; font-size: 16px; line-height: 1.6;">
                        Welcome to My Story Buddy, where imagination comes to life! We're excited to help you create magical stories that will spark creativity and wonder.
                    </p>
                    
                    <p style="margin: 0 0 20px 0; color: #666; font-size: 16px; line-height: 1.6;">
                        With My Story Buddy, you can:
                    </p>
                    
                    <ul style="margin: 0 0 30px 0; color: #666; font-size: 16px; line-height: 1.8;">
                        <li>Generate personalized stories based on your ideas</li>
                        <li>Choose from multiple formats: text stories and comic books</li>
                        <li>Enjoy beautiful illustrations that bring your stories to life</li>
                        <li>Learn fun facts while your stories are being created</li>
                    </ul>
                    
                    <div style="text-align: center; margin: 40px 0;">
                        <div style="display: inline-block; background: #E8E3FF; border-radius: 12px; padding: 20px 30px;">
                            <p style="margin: 0; color: #1a1a1a; font-size: 18px; font-weight: 600;">
                                Ready to start your storytelling adventure? 📖✨
                            </p>
                        </div>
                    </div>
                    
                    <p style="margin: 0; color: #666; font-size: 16px; line-height: 1.6;">
                        Start by entering any topic or idea that interests you, and watch as we transform it into an engaging story just for you!
                    </p>
                </div>
                
                <!-- Footer -->
                <div style="background: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #f0f0f0;">
                    <p style="margin: 0; color: #999; font-size: 14px;">
                        Happy storytelling! 📚✨<br>
                        The My Story Buddy Team
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_welcome_email_text(self, first_name: str) -> str:
        """Create text content for welcome email"""
        return f"""
        Hi {first_name}!

        Welcome to My Story Buddy, where imagination comes to life! We're excited to help you create magical stories that will spark creativity and wonder.

        With My Story Buddy, you can:
        • Generate personalized stories based on your ideas
        • Choose from multiple formats: text stories and comic books
        • Enjoy beautiful illustrations that bring your stories to life
        • Learn fun facts while your stories are being created

        Ready to start your storytelling adventure? 📖✨

        Start by entering any topic or idea that interests you, and watch as we transform it into an engaging story just for you!

        Happy storytelling! 📚✨
        The My Story Buddy Team
        """

# Global email service instance
email_service = EmailService()