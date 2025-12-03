#!/usr/bin/env python3
"""
GRE Vocabulary Guide Generator

Parses responses.json and generates an HTML vocabulary guide
similar to episode-guide.html format.
"""

import json
import re
from pathlib import Path


def clean_response_text(text: str) -> str:
    """Remove model prompt phrases like 'Of course', 'Absolutely', etc."""
    # Patterns to remove at the beginning of responses
    patterns_to_remove = [
        r"^Of course\.?\s*",
        r"^Absolutely\.?\s*",
        r"^No problem\.?\s*",
        r"^You got it\.?\s*",
        r"^Sure\.?\s*",
        r"^Certainly\.?\s*",
        r"^Here (?:is|are) .*?:\s*",
        r"^Let's continue.*?\.\s*",
        r"^Let's keep going.*?\.\s*",
        r"^Let's pick up where we left off.*?\.\s*",
        r"^My apologies.*?\.\s*",
        r"^Apologies for.*?\.\s*",
    ]
    
    for pattern in patterns_to_remove:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
    
    return text.strip()


def parse_vocab_entry(line: str) -> dict | None:
    """Parse a vocabulary entry line into word, mnemonic, and definition."""
    # Pattern: Word - Mnemonic: ... Definition: ...
    # Or: Word - Mnemonic: ... \n\nDefinition: ...
    
    # Try to match the pattern with Definition on the same line
    match = re.match(
        r'^([A-Za-z\s]+)\s*-\s*Mnemonic:\s*(.+?)\s*Definition:\s*(.+?)\.?$',
        line.strip(),
        re.IGNORECASE
    )
    
    if match:
        return {
            'word': match.group(1).strip(),
            'mnemonic': match.group(2).strip().rstrip('.'),
            'definition': match.group(3).strip().rstrip('.')
        }
    
    # Try simpler pattern without "Definition:" prefix
    match = re.match(
        r'^([A-Za-z\s]+)\s*-\s*Mnemonic:\s*(.+?)$',
        line.strip(),
        re.IGNORECASE
    )
    
    if match:
        return {
            'word': match.group(1).strip(),
            'mnemonic': match.group(2).strip().rstrip('.'),
            'definition': ''
        }
    
    return None


def parse_response(text: str) -> list[dict]:
    """Parse a response text to extract groups and vocabulary entries."""
    text = clean_response_text(text)
    groups = []
    
    # Split by group headers
    group_pattern = r'Group\s+(\d+)'
    parts = re.split(group_pattern, text)
    
    # parts will be: [preamble, group_num, content, group_num, content, ...]
    i = 1
    while i < len(parts) - 1:
        group_num = int(parts[i])
        group_content = parts[i + 1]
        
        entries = []
        lines = group_content.strip().split('\n')
        
        current_word = None
        current_mnemonic = None
        current_definition = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a word entry with mnemonic (Groups 1-30 format)
            # Pattern: Word - Mnemonic: ... Definition: ...
            word_mnemonic_match = re.match(r'^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s*-\s*Mnemonic:\s*(.+)$', line, re.IGNORECASE)
            
            # Check if this is a word entry with definition first (Groups 31-34 format)
            # Pattern: word - Definition text.
            word_def_match = re.match(r'^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s*-\s*(?!Mnemonic)(.+)$', line, re.IGNORECASE)
            
            if word_mnemonic_match:
                # Save previous entry if exists
                if current_word and (current_definition or current_mnemonic):
                    entries.append({
                        'word': current_word,
                        'mnemonic': current_mnemonic or '',
                        'definition': current_definition or ''
                    })
                
                current_word = word_mnemonic_match.group(1).strip()
                mnemonic_and_maybe_def = word_mnemonic_match.group(2).strip()
                
                # Check if definition is on same line
                def_match = re.search(r'Definition:\s*(.+?)\.?$', mnemonic_and_maybe_def, re.IGNORECASE)
                if def_match:
                    current_mnemonic = re.sub(r'\s*Definition:.*$', '', mnemonic_and_maybe_def, flags=re.IGNORECASE).strip().rstrip('.')
                    current_definition = def_match.group(1).strip().rstrip('.')
                else:
                    current_mnemonic = mnemonic_and_maybe_def.rstrip('.')
                    current_definition = None
            
            # Check if this is a standalone Mnemonic line (Groups 31-34 format)
            elif line.lower().startswith('mnemonic:'):
                mnemonic_text = re.sub(r'^mnemonic:\s*', '', line, flags=re.IGNORECASE)
                current_mnemonic = mnemonic_text.strip().rstrip('.')
            
            # Check if this is a standalone definition line
            elif line.lower().startswith('definition:'):
                def_text = re.sub(r'^definition:\s*', '', line, flags=re.IGNORECASE)
                current_definition = def_text.strip().rstrip('.')
            
            # Check for word - definition format (Groups 31-34 style)
            # Only match if we don't have a current word being built
            elif word_def_match and current_word is None:
                # Save any previous entry
                if current_word and (current_definition or current_mnemonic):
                    entries.append({
                        'word': current_word,
                        'mnemonic': current_mnemonic or '',
                        'definition': current_definition or ''
                    })
                
                current_word = word_def_match.group(1).strip()
                current_definition = word_def_match.group(2).strip().rstrip('.')
                current_mnemonic = None
            
            # Handle case where we have a current word and encounter a new word-def pattern
            elif word_def_match and current_word is not None:
                # Save current entry
                entries.append({
                    'word': current_word,
                    'mnemonic': current_mnemonic or '',
                    'definition': current_definition or ''
                })
                
                # Start new entry
                current_word = word_def_match.group(1).strip()
                current_definition = word_def_match.group(2).strip().rstrip('.')
                current_mnemonic = None
        
        # Don't forget the last entry
        if current_word and (current_definition or current_mnemonic):
            entries.append({
                'word': current_word,
                'mnemonic': current_mnemonic or '',
                'definition': current_definition or ''
            })
        
        if entries:
            groups.append({
                'number': group_num,
                'entries': entries
            })
        
        i += 2
    
    return groups


def generate_html(all_groups: list[dict]) -> str:
    """Generate the complete HTML document."""
    
    # Sort groups by number
    all_groups.sort(key=lambda x: x['number'])
    
    # Calculate total words
    total_words = sum(len(g['entries']) for g in all_groups)
    
    # Define episodes (groups of groups)
    episodes = [
        {'name': 'Episode 1: Groups 1–4', 'desc': 'Foundation vocabulary', 'groups': range(1, 5)},
        {'name': 'Episode 2: Groups 5–9', 'desc': 'Building blocks', 'groups': range(5, 10)},
        {'name': 'Episode 3: Groups 10–14', 'desc': 'Advanced concepts', 'groups': range(10, 15)},
        {'name': 'Episode 4: Groups 15–19', 'desc': 'Expanding horizons', 'groups': range(15, 20)},
        {'name': 'Episode 5: Groups 20–24', 'desc': 'Deepening knowledge', 'groups': range(20, 25)},
        {'name': 'Episode 6: Groups 25–29', 'desc': 'Mastery level', 'groups': range(25, 30)},
        {'name': 'Episode 7: Groups 30–34', 'desc': 'Expert vocabulary', 'groups': range(30, 35)},
    ]
    
    # Create group lookup
    group_lookup = {g['number']: g for g in all_groups}
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GRE Vocabulary - Complete Reference</title>
  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}
    
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      line-height: 1.6;
      color: #e8e6f0;
      background: linear-gradient(135deg, #2d3561 0%, #3d2d52 100%);
      min-height: 100vh;
      padding: 20px;
    }}
    
    .container {{
      max-width: 1200px;
      margin: 0 auto;
      background: #1e1e2e;
      border-radius: 12px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      overflow: hidden;
    }}
    
    header {{
      background: #b4a7d6;
      color: #1e1e2e;
      padding: 40px;
      text-align: center;
    }}
    
    header h1 {{
      font-size: 2.5em;
      margin-bottom: 10px;
      font-weight: 700;
    }}
    
    header p {{
      font-size: 1.2em;
      opacity: 0.85;
    }}
    
    .toc {{
      background: #252535;
      padding: 30px 40px;
      border-bottom: 3px solid #8b9dc3;
    }}
    
    .toc h2 {{
      color: #b4a7d6;
      margin-bottom: 20px;
      font-size: 1.8em;
    }}
    
    .toc-episodes {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 15px;
    }}
    
    .toc-episode {{
      background: #2a2a3e;
      padding: 15px 20px;
      border-radius: 8px;
      border-left: 4px solid #8b9dc3;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    
    .toc-episode:hover {{
      transform: translateX(5px);
      box-shadow: 0 4px 12px rgba(139, 157, 195, 0.3);
    }}
    
    .toc-episode h3 {{
      color: #a8c0ff;
      margin-bottom: 10px;
      font-size: 1.2em;
    }}
    
    .toc-episode ul {{
      list-style: none;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    
    .toc-episode a {{
      color: #deb4e8;
      text-decoration: none;
      font-size: 0.9em;
      padding: 4px 10px;
      background: #353545;
      border-radius: 4px;
      transition: background 0.2s;
    }}
    
    .toc-episode a:hover {{
      background: #8b9dc3;
      color: #1e1e2e;
    }}
    
    .episode {{
      padding: 40px;
      border-bottom: 2px solid #2a2a3e;
    }}
    
    .episode:last-child {{
      border-bottom: none;
    }}
    
    .episode-header {{
      text-align: center;
      margin-bottom: 30px;
      padding-bottom: 20px;
      border-bottom: 3px solid #8b9dc3;
    }}
    
    .episode-header h2 {{
      color: #a8c0ff;
      font-size: 2em;
      margin-bottom: 10px;
    }}
    
    .episode-header p {{
      color: #b4a7d6;
      font-size: 1.1em;
    }}
    
    .group {{
      margin-bottom: 40px;
      background: #252535;
      border-radius: 8px;
      padding: 20px;
      border-left: 5px solid #deb4e8;
    }}
    
    .group-title {{
      color: #deb4e8;
      font-size: 1.5em;
      margin-bottom: 15px;
      font-weight: 600;
    }}
    
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #2a2a3e;
      border-radius: 6px;
      overflow: hidden;
    }}
    
    th {{
      background: #b4a7d6;
      color: #1e1e2e;
      padding: 12px;
      text-align: left;
      font-weight: 600;
      font-size: 1.1em;
    }}
    
    td {{
      padding: 10px 12px;
      border-bottom: 1px solid #353545;
      color: #e8e6f0;
    }}
    
    tr:last-child td {{
      border-bottom: none;
    }}
    
    tr:hover {{
      background: #2f2f45;
    }}
    
    td:first-child {{
      font-weight: 600;
      color: #a8c0ff;
      width: 20%;
    }}
    
    td:nth-child(2) {{
      color: #c9c4d9;
      width: 50%;
      font-style: italic;
    }}
    
    td:last-child {{
      color: #e8e6f0;
      width: 30%;
    }}
    
    .back-to-top {{
      position: fixed;
      bottom: 30px;
      right: 30px;
      background: linear-gradient(135deg, #8b9dc3 0%, #b4a7d6 100%);
      color: #1e1e2e;
      width: 50px;
      height: 50px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      font-size: 1.5em;
      box-shadow: 0 4px 12px rgba(139, 157, 195, 0.4);
      transition: transform 0.2s;
      font-weight: bold;
    }}
    
    .back-to-top:hover {{
      transform: scale(1.1);
    }}
    
    @media (max-width: 768px) {{
      body {{
        padding: 10px;
      }}
      
      header {{
        padding: 20px;
      }}
      
      header h1 {{
        font-size: 1.8em;
      }}
      
      .toc, .episode {{
        padding: 20px;
      }}
      
      .toc-episodes {{
        grid-template-columns: 1fr;
      }}
      
      td:nth-child(2) {{
        display: none;
      }}
      
      td:first-child {{
        width: 40%;
      }}
      
      td:last-child {{
        width: 60%;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>GRE Vocabulary Reference</h1>
      <p>Complete collection of {total_words} essential words across {len(all_groups)} groups</p>
    </header>
    
    <nav class="toc" id="toc">
      <h2>📚 Table of Contents</h2>
      <div class="toc-episodes">
'''
    
    # Generate TOC
    for episode in episodes:
        html += f'''        <div class="toc-episode">
          <h3>{episode['name']}</h3>
          <p style="margin-bottom: 10px; color: #b4a7d6;">{episode['desc']}</p>
          <ul>
'''
        for gnum in episode['groups']:
            if gnum in group_lookup:
                html += f'            <li><a href="#group{gnum}">Group {gnum}</a></li>\n'
        html += '''          </ul>
        </div>
'''
    
    html += '''      </div>
    </nav>
'''
    
    # Generate episode sections
    for episode in episodes:
        episode_groups = [group_lookup[gnum] for gnum in episode['groups'] if gnum in group_lookup]
        if not episode_groups:
            continue
        
        html += f'''
    <section class="episode">
      <div class="episode-header">
        <h2>{episode['name']}</h2>
        <p>{episode['desc']}</p>
      </div>
'''
        
        for group in episode_groups:
            html += f'''
      <div class="group" id="group{group['number']}">
        <h3 class="group-title">Group {group['number']}</h3>
        <table>
          <thead>
            <tr>
              <th>Word</th>
              <th>Mnemonic</th>
              <th>Definition</th>
            </tr>
          </thead>
          <tbody>
'''
            for entry in group['entries']:
                word = entry['word'].title()
                mnemonic = entry.get('mnemonic', '') or ''
                definition = entry.get('definition', '') or ''
                
                # Escape HTML characters
                mnemonic = mnemonic.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                definition = definition.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                html += f'            <tr><td>{word}</td><td>{mnemonic}</td><td>{definition}</td></tr>\n'
            
            html += '''          </tbody>
        </table>
      </div>
'''
        
        html += '''    </section>
'''
    
    html += '''  </div>
  
  <a href="#toc" class="back-to-top">↑</a>
</body>
</html>
'''
    
    return html


def main():
    # Read responses.json
    script_dir = Path(__file__).parent
    responses_path = script_dir / 'responses.json'
    output_path = script_dir / 'vocab-guide-generated.html'
    
    print(f"Reading {responses_path}...")
    
    with open(responses_path, 'r', encoding='utf-8') as f:
        responses = json.load(f)
    
    print(f"Found {len(responses)} responses to parse")
    
    # Parse all responses
    all_groups = []
    seen_groups = set()
    
    for i, response in enumerate(responses):
        print(f"Parsing response {i + 1}...")
        groups = parse_response(response)
        
        for group in groups:
            if group['number'] not in seen_groups:
                all_groups.append(group)
                seen_groups.add(group['number'])
                print(f"  Found Group {group['number']} with {len(group['entries'])} entries")
    
    print(f"\nTotal: {len(all_groups)} groups")
    print(f"Total words: {sum(len(g['entries']) for g in all_groups)}")
    
    # Generate HTML
    print(f"\nGenerating HTML...")
    html = generate_html(all_groups)
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Generated: {output_path}")
    print("Done!")


if __name__ == '__main__':
    main()
