# File: brainstorming_tab.py

import os
import sqlite3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                           QTextEdit, QPushButton, QComboBox, QLabel, QFrame,
                           QMessageBox, QDateEdit, QScrollArea)
from PyQt5.QtCore import Qt, QTimer, QDate
from PyQt5.QtGui import QFont
from database_manager import DatabaseManager
import anthropic
from datetime import datetime
from dotenv import load_dotenv
import json

class ContextManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.active_context = {
            'characters': {},  # Character profiles
            'events': {},      # Event details
            'locations': {},   # Location details
            'entities': {},    # Entity details
            'relationships': {} # Tracked relationships
        }
        self.pending_expansions = []  # Potential context expansions identified by Claude

    def add_character_context(self, character_name):
        """Add character and their basic related information to context"""
        try:
            cursor = self.db_manager.conn.cursor()
            
            # Get character profile
            cursor.execute("""
                SELECT * FROM Characters 
                WHERE DisplayName = ? OR Aliases LIKE ?
            """, (character_name, f"%{character_name}%"))
            
            character = cursor.fetchone()
            if character:
                # Store all character fields in context
                desc = cursor.description
                character_dict = {desc[i][0]: value for i, value in enumerate(character)}
                self.active_context['characters'][character_name] = character_dict
                return True
            return False
            
        except sqlite3.Error as e:
            print(f"Error adding character context: {e}")
            return False

    def add_event_context(self, event_id):
        """Add event and related information to context"""
        try:
            cursor = self.db_manager.conn.cursor()
            
            # Get event details
            cursor.execute("""
                SELECT * FROM Events WHERE EventID = ?
            """, (event_id,))
            
            event = cursor.fetchone()
            if event:
                desc = cursor.description
                event_dict = {desc[i][0]: value for i, value in enumerate(event)}
                self.active_context['events'][event_id] = event_dict
                return True
            return False
            
        except sqlite3.Error as e:
            print(f"Error adding event context: {e}")
            return False

    def identify_potential_expansions(self, text):
        """Identify names and references that could be expanded"""
        try:
            cursor = self.db_manager.conn.cursor()
            
            # Get all character names and aliases
            cursor.execute("SELECT DisplayName, Aliases FROM Characters")
            characters = cursor.fetchall()
            
            expansions = []
            for display_name, aliases in characters:
                # Check if name appears in text but isn't in active context
                if display_name in text and display_name not in self.active_context['characters']:
                    expansions.append(('character', display_name))
                
                # Check aliases if they exist
                if aliases:
                    alias_list = aliases.split(',')
                    for alias in alias_list:
                        alias = alias.strip()
                        if alias in text and display_name not in self.active_context['characters']:
                            expansions.append(('character', display_name))
                            break
            
            self.pending_expansions = expansions
            return expansions
            
        except sqlite3.Error as e:
            print(f"Error identifying expansions: {e}")
            return []

    def expand_context(self, expansion_type, identifier):
        """Expand context based on approved expansion"""
        if expansion_type == 'character':
            return self.add_character_context(identifier)
        # Add more expansion types as needed
        return False

    def get_context_summary(self):
        """Return a summary of current context"""
        return {
            'num_characters': len(self.active_context['characters']),
            'num_events': len(self.active_context['events']),
            'active_characters': list(self.active_context['characters'].keys())
        }

    def format_context_for_prompt(self):
        """Format current context for Claude's consumption"""
        prompt_parts = []
        
        # Add character profiles
        if self.active_context['characters']:
            prompt_parts.append("CHARACTER PROFILES:")
            for char_name, char_data in self.active_context['characters'].items():
                prompt_parts.append(f"\n{char_name}:")
                for field, value in char_data.items():
                    if value and field not in ['CharacterID']:  # Skip empty fields and ID
                        prompt_parts.append(f"- {field}: {value}")
        
        # Add events
        if self.active_context['events']:
            prompt_parts.append("\nRELATED EVENTS:")
            for event_id, event_data in self.active_context['events'].items():
                prompt_parts.append(f"\n{event_data['EventDate']}: {event_data['EventTitle']}")
                prompt_parts.append(event_data['EventText'])
        
        return "\n".join(prompt_parts)

    def clear_context(self):
        """Clear all active context"""
        self.active_context = {
            'characters': {},
            'events': {},
            'locations': {},
            'entities': {},
            'relationships': {}
        }
        self.pending_expansions = []

class BrainstormingTab(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Load API key from environment variables
        load_dotenv()
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # Initialize context manager
        self.context_manager = ContextManager(self.db_manager)
        
        self.current_session_id = None
        self.conversation_history = []
        self.create_brainstorming_table()
        self.initUI()
        self.load_dropdowns()

    def create_brainstorming_table(self):
        """Create table to store brainstorming sessions and their development"""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS BrainstormingSessions (
                    SessionID INTEGER PRIMARY KEY AUTOINCREMENT,
                    SessionName TEXT,
                    CreatedDate TEXT,
                    LastModified TEXT,
                    Scope TEXT,
                    ConversationHistory TEXT,
                    DevelopmentContent TEXT,
                    ActiveContext TEXT,
                    Status TEXT
                )
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating brainstorming table: {e}")
            QMessageBox.critical(self, "Database Error", 
                               f"Failed to create brainstorming table: {str(e)}")

    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Create main splitter
        self.splitter = QSplitter(Qt.Horizontal)

        # Left panel - Context Selection
        left_panel = self.create_left_panel()
        self.splitter.addWidget(left_panel)

        # Middle panel - Conversation
        middle_panel = self.create_middle_panel()
        self.splitter.addWidget(middle_panel)

        # Right panel - Development Output
        right_panel = self.create_right_panel()
        self.splitter.addWidget(right_panel)

        # Add splitter to main layout
        layout.addWidget(self.splitter)

        # Set initial splitter sizes (25%, 50%, 25%)
        self.splitter.setSizes([int(self.width() * 0.25), 
                              int(self.width() * 0.50), 
                              int(self.width() * 0.25)])

    def create_left_panel(self):
        panel = QFrame()
        layout = QVBoxLayout()
        
        # Session management
        session_layout = QHBoxLayout()
        self.session_combo = QComboBox()
        self.session_combo.addItem("New Session...")
        self.session_combo.currentTextChanged.connect(self.on_session_changed)
        session_layout.addWidget(QLabel("Session:"))
        session_layout.addWidget(self.session_combo)
        layout.addLayout(session_layout)
        
        # Date Range
        date_layout = QVBoxLayout()
        date_layout.addWidget(QLabel("Date Range:"))
        
        # From Date
        from_layout = QHBoxLayout()
        from_layout.addWidget(QLabel("From:"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate(1890, 1, 1))
        from_layout.addWidget(self.from_date)
        date_layout.addLayout(from_layout)
        
        # To Date
        to_layout = QHBoxLayout()
        to_layout.addWidget(QLabel("To:"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate(1899, 12, 31))
        to_layout.addWidget(self.to_date)
        date_layout.addLayout(to_layout)
        
        layout.addLayout(date_layout)
        
        # Context filters
        layout.addWidget(QLabel("Initial Context:"))
        
        self.character_combo = QComboBox()
        self.character_combo.addItem("All Characters")
        layout.addWidget(self.character_combo)
        
        self.location_combo = QComboBox()
        self.location_combo.addItem("All Locations")
        layout.addWidget(self.location_combo)
        
        self.entity_combo = QComboBox()
        self.entity_combo.addItem("All Entities")
        layout.addWidget(self.entity_combo)
        
        # Buttons
        self.apply_btn = QPushButton("Apply Filters")
        self.apply_btn.clicked.connect(self.apply_filters)
        layout.addWidget(self.apply_btn)
        
        self.clear_filters_btn = QPushButton("Clear Filters")
        self.clear_filters_btn.clicked.connect(self.clear_filters)
        layout.addWidget(self.clear_filters_btn)
        
        # Context summary
        layout.addWidget(QLabel("Active Context:"))
        self.context_summary = QTextEdit()
        self.context_summary.setReadOnly(True)
        self.context_summary.setMaximumHeight(100)
        layout.addWidget(self.context_summary)
        
        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def create_middle_panel(self):
        panel = QFrame()
        layout = QVBoxLayout()
        
        # Clear conversation button
        self.clear_conv_btn = QPushButton("Clear Conversation")
        self.clear_conv_btn.clicked.connect(self.clear_conversation)
        layout.addWidget(self.clear_conv_btn)
        
        # Conversation history
        self.conversation_display = QTextEdit()
        self.conversation_display.setReadOnly(True)
        layout.addWidget(self.conversation_display, stretch=7)
        
        # Input area
        input_layout = QHBoxLayout()
        self.input_box = QTextEdit()
        self.input_box.setMaximumHeight(100)
        input_layout.addWidget(self.input_box)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout, stretch=1)
        
        panel.setLayout(layout)
        return panel

    def create_right_panel(self):
        panel = QFrame()
        layout = QVBoxLayout()
        
        # Header for Development Notes
        header_layout = QHBoxLayout()
        layout.addWidget(QLabel("Development Notes"))
        
        # Add buttons for managing content
        button_layout = QHBoxLayout()
        self.capture_btn = QPushButton("Capture Suggestion")
        self.capture_btn.clicked.connect(self.capture_suggestion)
        self.capture_btn.setEnabled(False)  # Only enable when there's a suggestion to capture
        button_layout.addWidget(self.capture_btn)
        
        self.clear_notes_btn = QPushButton("Clear Notes")
        self.clear_notes_btn.clicked.connect(self.clear_development_notes)
        button_layout.addWidget(self.clear_notes_btn)
        
        layout.addLayout(button_layout)
        
        # Development output with categories
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)  # Make it read-only
        layout.addWidget(self.output_display, stretch=1)
        
        # Save button
        save_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Session")
        self.save_btn.clicked.connect(self.save_session)
        save_layout.addWidget(self.save_btn)
        layout.addLayout(save_layout)
        
        panel.setLayout(layout)
        return panel

    def capture_suggestion(self):
        """Capture the latest suggestion into development notes"""
        if not hasattr(self, 'latest_suggestion'):
            return
            
        current_text = self.output_display.toPlainText()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format the new content with timestamp
        new_content = f"\n{'='*50}\n"
        new_content += f"Captured at: {timestamp}\n"
        new_content += f"{self.latest_suggestion}\n"
        
        # Append to existing content
        self.output_display.setPlainText(current_text + new_content)
        self.capture_btn.setEnabled(False)
        
        # Add confirmation to conversation
        self.add_to_conversation("System", "Development note captured.")

    def clear_development_notes(self):
        """Clear the development notes panel"""
        reply = QMessageBox.question(self, 'Clear Notes',
                                "Are you sure you want to clear all development notes?",
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.output_display.clear()
            self.add_to_conversation("System", "Development notes cleared.")

    def load_dropdowns(self):
        """Load data into the dropdown menus"""
        try:
            # Characters
            self.character_combo.clear()
            self.character_combo.addItem("All Characters")
            self.cursor.execute("SELECT DisplayName FROM Characters ORDER BY DisplayName")
            characters = self.cursor.fetchall()
            for character in characters:
                self.character_combo.addItem(character[0])
            
            # Locations
            self.location_combo.clear()
            self.location_combo.addItem("All Locations")
            self.cursor.execute("SELECT DisplayName FROM Locations ORDER BY DisplayName")
            locations = self.cursor.fetchall()
            for location in locations:
                self.location_combo.addItem(location[0])
            
            # Entities
            self.entity_combo.clear()
            self.entity_combo.addItem("All Entities")
            self.cursor.execute("SELECT DisplayName FROM Entities ORDER BY DisplayName")
            entities = self.cursor.fetchall()
            for entity in entities:
                self.entity_combo.addItem(entity[0])
                
        except sqlite3.Error as e:
            print(f"Error loading dropdown data: {e}")
            QMessageBox.warning(self, "Database Error", 
                              f"Failed to load dropdown data: {str(e)}")

    def update_context_summary(self):
        """Update the context summary display"""
        summary = self.context_manager.get_context_summary()
        summary_text = f"Active Characters: {', '.join(summary['active_characters'])}\n"
        summary_text += f"Total Events: {summary['num_events']}"
        self.context_summary.setText(summary_text)

    def clear_filters(self):
        """Reset all filters to default values"""
        self.from_date.setDate(QDate(1890, 1, 1))
        self.to_date.setDate(QDate(1899, 12, 31))
        self.character_combo.setCurrentText("All Characters")
        self.location_combo.setCurrentText("All Locations")
        self.entity_combo.setCurrentText("All Entities")
        self.context_manager.clear_context()
        self.update_context_summary()
        self.add_to_conversation("System", "Filters and context have been cleared")

    def clear_conversation(self):
        """Clear the conversation display and history"""
        self.conversation_display.clear()
        self.conversation_history = []
        self.add_to_conversation("System", "Conversation cleared")

    def apply_filters(self):
        """Apply selected filters and build initial context"""
        try:
            # Clear previous context
            self.context_manager.clear_context()
            
            # Build query based on selections
            query_parts = []
            params = []
            
            # Date range
            from_date = self.from_date.date().toString("yyyy-MM-dd")
            to_date = self.to_date.date().toString("yyyy-MM-dd")
            query_parts.append("EventDate BETWEEN ? AND ?")
            params.extend([from_date, to_date])
            
            # Selected character
            if self.character_combo.currentText() != "All Characters":
                char_name = self.character_combo.currentText()
                self.context_manager.add_character_context(char_name)
                query_parts.append("""
                    EventID IN (
                        SELECT EventID FROM EventCharacters 
                        JOIN Characters ON EventCharacters.CharacterID = Characters.CharacterID 
                        WHERE Characters.DisplayName = ?
                    )
                """)
                params.append(char_name)
            
            # Add similar blocks for Location and Entity...
            
            # Construct and execute query
            query = "SELECT * FROM Events WHERE " + " AND ".join(query_parts)
            self.cursor.execute(query, params)
            events = self.cursor.fetchall()
            
            # Add events to context
            for event in events:
                self.context_manager.add_event_context(event[0])  # event[0] is EventID
            
            self.update_context_summary()
            self.add_to_conversation("System", 
                f"Context loaded successfully. Found {len(events)} relevant events.")
            
        except sqlite3.Error as e:
            print(f"Error applying filters: {e}")
            QMessageBox.warning(self, "Database Error", 
                              f"Failed to apply filters: {str(e)}")

    def send_message(self):
        """Send user message and get AI response"""
        user_message = self.input_box.toPlainText().strip()
        if not user_message:
            return
            
        # Add user message to conversation
        self.add_to_conversation("User", user_message)
        self.input_box.clear()
        
        try:
            # Get current context
            context = self.context_manager.format_context_for_prompt()
            
            # Construct the system message
            system_message = """You are a creative writing partner with access to a historical database. 
            Your role is to help explore and develop stories based on real historical events and people.
            
            When the conversation reveals significant story elements, character insights, or narrative 
            possibilities, you should offer to formalize these into development notes. Your suggestions 
            should be clear, structured, and focused on storytelling potential while maintaining 
            historical accuracy.

            When suggesting content for development notes, use clear headers and organize information into 
            relevant categories such as:
            - KEY EVENTS: Significant historical moments with dates
            - CHARACTER INSIGHTS: Understanding of motivations and relationships
            - STORY ANGLES: Potential narrative approaches or themes
            - HISTORICAL CONTEXT: Important background information
            - QUESTIONS TO EXPLORE: Areas needing further investigation

            Always:
            1. Base responses on provided historical context
            2. Indicate when speculating vs working from historical records
            3. Ask permission before expanding scope
            4. Cite specific sources when referencing events
            5. Suggest capturing development notes when the conversation yields valuable story elements"""
            
            # Construct the conversation prompt
            prompt = f"""Based on the following historical context and our conversation, 
            let's explore the narrative possibilities while maintaining historical accuracy.

            Current Historical Context:
            {context}

            Previous Development Notes:
            {self.output_display.toPlainText()}

            User Query:
            {user_message}"""
            
            # Get response from Claude
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                temperature=0.7,
                system=system_message,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Process the response
            ai_response = response.content[0].text
            
            # Look for suggestion markers
            if "SUGGESTED DEVELOPMENT NOTES:" in ai_response:
                # Split response into conversation part and suggestion part
                parts = ai_response.split("SUGGESTED DEVELOPMENT NOTES:")
                conversation_response = parts[0]
                self.latest_suggestion = parts[1].strip()
                self.capture_btn.setEnabled(True)
                
                # Add note about available suggestion
                ai_response = conversation_response + "\n\nI've prepared some development notes based on our discussion. Would you like to capture them? Use the 'Capture Suggestion' button if you'd like to add these to your development notes."
            
            # Check for potential context expansions
            expansions = self.context_manager.identify_potential_expansions(ai_response)
            if expansions:
                expansion_msg = "\n\nI notice references to additional people/places that might be relevant. "
                expansion_msg += "Would you like me to include context about: "
                expansion_msg += ", ".join([f"{exp[1]}" for exp in expansions]) + "?"
                ai_response += expansion_msg
            
            # Add AI response to conversation
            self.add_to_conversation("Claude", ai_response)
            
        except Exception as e:
            print(f"Error getting AI response: {e}")
            self.add_to_conversation("System", f"Error: Failed to get AI response: {str(e)}")

    def add_to_conversation(self, speaker, message):
        """Add a message to the conversation history"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {speaker}: {message}\n"
        self.conversation_history.append(formatted_message)
        self.conversation_display.append(formatted_message)

    def save_session(self):
        """Save current session to database"""
        try:
            # Format conversation history and development content
            conversation_text = "".join(self.conversation_history)
            development_text = self.output_display.toPlainText()
            
            # Serialize active context
            context_json = json.dumps(self.context_manager.active_context)
            
            if self.current_session_id:
                # Update existing session
                self.cursor.execute("""
                    UPDATE BrainstormingSessions 
                    SET LastModified = ?, ConversationHistory = ?, 
                        DevelopmentContent = ?, ActiveContext = ?
                    WHERE SessionID = ?
                """, (
                    datetime.now().isoformat(),
                    conversation_text,
                    development_text,
                    context_json,
                    self.current_session_id
                ))
            else:
                # Create new session
                self.cursor.execute("""
                    INSERT INTO BrainstormingSessions 
                    (SessionName, CreatedDate, LastModified, 
                        ConversationHistory, DevelopmentContent, ActiveContext, Status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"Session_{datetime.now().strftime('%Y%m%d_%H%M')}",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    conversation_text,
                    development_text,
                    context_json,
                    'In Progress'
                ))
                self.current_session_id = self.cursor.lastrowid
            
            self.conn.commit()
            QMessageBox.information(self, "Success", "Session saved successfully!")
            
        except sqlite3.Error as e:
            print(f"Error saving session: {e}")
            QMessageBox.warning(self, "Database Error", 
                                f"Failed to save session: {str(e)}")

    def on_session_changed(self, session_name):
        """Handle session selection changes"""
        if session_name == "New Session...":
            self.current_session_id = None
            self.conversation_history = []
            self.conversation_display.clear()
            self.output_display.clear()
            self.context_manager.clear_context()
            self.update_context_summary()
            return
            
        try:
            session_id = self.session_combo.currentData()
            self.cursor.execute("""
                SELECT ConversationHistory, DevelopmentContent, ActiveContext
                FROM BrainstormingSessions 
                WHERE SessionID = ?
            """, (session_id,))
            
            session_data = self.cursor.fetchone()
            if session_data:
                self.current_session_id = session_id
                
                # Restore conversation
                self.conversation_history = []
                self.conversation_display.clear()
                if session_data[0]:  # ConversationHistory
                    for line in session_data[0].split('\n'):
                        if line:
                            self.conversation_display.append(line)
                            self.conversation_history.append(line + '\n')
                
                # Restore development content
                self.output_display.setPlainText(session_data[1] or "")
                
                # Restore context
                if session_data[2]:  # ActiveContext
                    self.context_manager.active_context = json.loads(session_data[2])
                    self.update_context_summary()
                    
        except sqlite3.Error as e:
            print(f"Error loading session data: {e}")
            QMessageBox.warning(self, "Database Error", 
                                f"Failed to load session data: {str(e)}")