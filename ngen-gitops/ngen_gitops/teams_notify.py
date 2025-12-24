"""Teams notification module for sending webhook notifications."""
import json
from typing import Dict, Any, Optional

import requests

from .config import get_teams_webhook


def send_teams_notification(title: str, message: str, color: str = "0078D4", 
                            facts: Optional[Dict[str, str]] = None) -> bool:
    """Send notification to Microsoft Teams via webhook.
    
    Args:
        title: Notification title
        message: Notification message
        color: Theme color in hex (default: blue 0078D4)
        facts: Optional dictionary of facts to display
        
    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    webhook_url = get_teams_webhook()
    
    if not webhook_url:
        # No webhook configured, skip silently
        return False
    
    # Build Teams message card
    card = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": color,
        "title": title,
        "text": message
    }
    
    # Add facts if provided
    if facts:
        card["sections"] = [{
            "facts": [{"name": k, "value": v} for k, v in facts.items()]
        }]
    
    try:
        response = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(card),
            timeout=5
        )
        
        if response.status_code == 200:
            return True
        else:
            print(f"⚠️  Teams notification failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Teams notification failed: {str(e)}")
        return False


def notify_branch_created(repo: str, src_branch: str, dest_branch: str, 
                         branch_url: str, user: Optional[str] = None) -> None:
    """Send notification for branch creation.
    
    Args:
        repo: Repository name
        src_branch: Source branch name
        dest_branch: Destination branch name
        branch_url: Branch URL
        user: User who triggered the action
    """
    facts = {
        "Repository": repo,
        "Source Branch": src_branch,
        "New Branch": dest_branch,
        "Branch URL": branch_url
    }
    if user:
        facts["Triggered By"] = user
        
    send_teams_notification(
        title=f"🌿 Branch Created: {dest_branch}",
        message=f"New branch created in repository **{repo}**",
        color="28A745",  # Green
        facts=facts
    )


def notify_image_updated(repo: str, branch: str, yaml_path: str, 
                        image: str, commit: str, user: Optional[str] = None) -> None:
    """Send notification for image update.
    
    Args:
        repo: Repository name
        branch: Branch name
        yaml_path: YAML file path
        image: New image
        commit: Commit message
        user: User who triggered the action
    """
    facts = {
        "Repository": repo,
        "Branch": branch,
        "YAML File": yaml_path,
        "New Image": image,
        "Commit": commit
    }
    if user:
        facts["Triggered By"] = user

    send_teams_notification(
        title=f"🖼️ Image Updated: {image}",
        message=f"Container image updated in repository **{repo}**",
        color="0078D4",  # Blue
        facts=facts
    )


def notify_pr_created(repo: str, src_branch: str, dest_branch: str, 
                     pr_id: int, pr_url: str, user: Optional[str] = None) -> None:
    """Send notification for pull request creation.
    
    Args:
        repo: Repository name
        src_branch: Source branch name
        dest_branch: Destination branch name
        pr_id: Pull request ID
        pr_url: Pull request URL
        user: User who triggered the action
    """
    facts = {
        "Repository": repo,
        "Source": src_branch,
        "Destination": dest_branch,
        "PR ID": f"#{pr_id}",
        "PR URL": pr_url
    }
    if user:
        facts["Triggered By"] = user

    send_teams_notification(
        title=f"🔄 Pull Request Created: #{pr_id}",
        message=f"New pull request created in repository **{repo}**",
        color="6F42C1",  # Purple
        facts=facts
    )


def notify_pr_merged(repo: str, pr_id: str, src_branch: str, dest_branch: str,
                    merge_commit: str, user: Optional[str] = None) -> None:
    """Send notification for pull request merge.
    
    Args:
        repo: Repository name
        pr_id: Pull request ID
        src_branch: Source branch name
        dest_branch: Destination branch name
        merge_commit: Merge commit hash
        user: User who triggered the action
    """
    facts = {
        "Repository": repo,
        "PR ID": f"#{pr_id}",
        "Source": src_branch,
        "Destination": dest_branch,
        "Merge Commit": merge_commit
    }
    if user:
        facts["Triggered By"] = user

    send_teams_notification(
        title=f"✅ Pull Request Merged: #{pr_id}",
        message=f"Pull request merged in repository **{repo}**",
        color="28A745",  # Green
        facts=facts
    )


def send_teams_adaptive_card(title: str, facts: list = None, 
                              webhook_url: Optional[str] = None,
                              body_items: list = None) -> bool:
    """Send Adaptive Card notification to Microsoft Teams.
    
    This uses the newer Adaptive Card format required by Teams webhook v2.
    
    Args:
        title: Card title
        facts: List of fact dictionaries with 'name' and 'value' keys (optional)
        webhook_url: Optional webhook URL override (uses config if not provided)
        body_items: Optional list of Adaptive Card items to override default content
        
    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    # Use provided webhook or fall back to config
    url = webhook_url if webhook_url else get_teams_webhook()
    
    if not url:
        print("⚠️  Teams webhook not configured. Set TEAMS_WEBHOOK in ~/.ngen-gitops/.env or use --teams-webhook")
        return False
    
    # helper to construct default body if body_items not provided
    if not body_items:
        body_items = [
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": title,
                        "weight": "bolder",
                        "size": "large",
                        "color": "accent"
                    }
                ]
            }
        ]
        
        if facts:
            body_items.append({
                "type": "Container",
                "items": [
                    {
                        "type": "FactSet",
                        "facts": facts
                    }
                ]
            })
    
    # Build Adaptive Card payload
    message = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body_items
                }
            }
        ]
    }
    
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(message),
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 202:
            return True
        else:
            print(f"⚠️  Teams notification failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Teams notification failed: {str(e)}")
        return False


def notify_commit_info(service: str, ref: str, commits: list, success: bool,
                       output: str = "", webhook_url: Optional[str] = None) -> bool:
    """Send commit info notification using Adaptive Card format.
    
    Args:
        service: Service/repository name
        ref: Branch or tag reference
        commits: List of commit dictionaries from git_log result
        success: Whether the git log operation was successful
        output: Raw text output from git command (optional)
        webhook_url: Optional webhook URL override
        
    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    if not commits:
        print("⚠️  No commits to notify")
        return False
    
    # Get the first/last commit
    commit = commits[0]
    
    # Extract commit info
    commit_hash = commit.get('hash', commit.get('commit', ''))[:7]
    
    # Construct the formatted message block
    # We use the provided raw output if available, otherwise fallback to minimal info
    display_text = ""
    
    if output:
        # Prepend the header lines requested by user
        header = f"📝 Commit Details: {commit_hash}\n" + ("=" * 80) + "\n"
        display_text = header + output
    else:
        # Fallback construction
        author = commit.get('author', 'Unknown')
        message = commit.get('subject', commit.get('message', ''))
        display_text = f"Commit: {commit_hash}\nAuthor: {author}\n\n{message}"
    
    # Create body items for custom layout
    header_text = f"📋 {service} : {ref}"
    
    body_items = [
        {
            "type": "Container",
            "style": "emphasis",
            "items": [
                {
                    "type": "TextBlock",
                    "text": header_text,
                    "weight": "bolder",
                    "size": "large",
                    "color": "accent"
                }
            ]
        },
        {
            "type": "Container",
            "items": [
                {
                    "type": "TextBlock",
                    "text": display_text,
                    "fontType": "Monospace",
                    "wrap": True,
                    "size": "Small"
                }
            ]
        }
    ]
    
    result = send_teams_adaptive_card(
        title=header_text,
        body_items=body_items,
        webhook_url=webhook_url
    )
    
    if result:
        print("✅ Notification sent to Teams!")
    
    return result
