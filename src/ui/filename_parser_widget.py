# File: filename_parser_widget.py

import json
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QInputDialog
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import pyqtSlot


def get_html_content():
    return '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script src="https://unpkg.com/react@17/umd/react.development.js"></script>
    <script src="https://unpkg.com/react@17/umd/react.development.js"></script>
    <script src="https://unpkg.com/react-dom@17/umd/react-dom.development.js"></script>
    <script src="https://unpkg.com/babel-standalone@6.26.0/babel.min.js"></script>
    <style>
    .main-container {
        margin: 0;
        padding: 0;
    }
    .content-container {
        margin-top: 0;
        padding-top: 0;
    }
        .segment-btn {
            margin: 2px;
            padding: 5px 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            cursor: pointer;
        }
        .display-field {
            padding: 5px;
            margin: 2px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background-color: white;
            text-align: center;
            min-height: 30px;
        }
        .selected { background-color: #e3f2fd; }
        
        /* Publication row colors */
        .publication { background-color: #c8e6c9; }
        .title { background-color: #a5d6a7; }
        .author { background-color: #81c784; }
        
        /* Date row colors */
        .year { background-color: #fff9c4; }
        .month { background-color: #fff59d; }
        .day { background-color: #ffd54f; }
        
        /* Issue row colors */
        .volume { background-color: #f8bbd0; }
        .issue { background-color: #f48fb1; }
        .page { background-color: #ec407a; }
        
        /* Other row colors */
        .doi { background-color: #c8e6c9; }
        .other1 { background-color: #a5d6a7; }
        .other2 { background-color: #81c784; }

        .button-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 5px;
        }
        
        .display-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }

        .instructions {
            margin: 10px 0;
            padding: 10px;
            background-color: #e3f2fd;
            border-radius: 4px;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div id="root"></div>
    <script type="text/babel">
        const FilenameParser = () => {
            const [filename, setFilename] = React.useState("");
            const [segments, setSegments] = React.useState([]);
            const [selectedSegment, setSelectedSegment] = React.useState(null);
            const [fieldAssignments, setFieldAssignments] = React.useState({
                publication: [],
                title: [],
                author: [],
                year: null,
                month: null,
                day: null,
                volume: null,
                issue: null,
                page: null,
                doi: [],
                other1: [],
                other2: []
            });

            React.useEffect(() => {
                window.updateFilename = (newFilename) => {
                    console.log("Original filename:", newFilename);
                    // Strip file extension and any duplicate indicators
                    const baseFilename = newFilename
                        .replace(/\.[^/.]+$/, "")  // Remove file extension
                        .replace(/\s*\(\d+\)\s*$/, "");  // Remove (1), (2), etc.
                    console.log("Processed filename:", baseFilename);
                    setFilename(baseFilename);
                    const splitSegments = baseFilename.split(/[_\s-]+/).map((text, index) => ({
                        text,
                        index
                    }));
                    setSegments(splitSegments);
                };

                window.clearFields = () => {
                    setFieldAssignments({
                        publication: [],
                        title: [],
                        author: [],
                        year: null,
                        month: null,
                        day: null,
                        volume: null,
                        issue: null,
                        page: null,
                        doi: [],
                        other1: [],
                        other2: []
                    });
                    setSelectedSegment(null);
                };
            }, []);

            const getSegmentClass = (segment) => {
                if (Array.isArray(fieldAssignments.publication) && fieldAssignments.publication.includes(segment.index)) return 'publication';
                if (Array.isArray(fieldAssignments.title) && fieldAssignments.title.includes(segment.index)) return 'title';
                if (Array.isArray(fieldAssignments.author) && fieldAssignments.author.includes(segment.index)) return 'author';
                if (fieldAssignments.year === segment.index) return 'year';
                if (fieldAssignments.month === segment.index) return 'month';
                if (fieldAssignments.day === segment.index) return 'day';
                if (fieldAssignments.volume === segment.index) return 'volume';
                if (fieldAssignments.issue === segment.index) return 'issue';
                if (fieldAssignments.page === segment.index) return 'page';
                if (Array.isArray(fieldAssignments.doi) && fieldAssignments.doi.includes(segment.index)) return 'doi';
                if (Array.isArray(fieldAssignments.other1) && fieldAssignments.other1.includes(segment.index)) return 'other1';
                if (Array.isArray(fieldAssignments.other2) && fieldAssignments.other2.includes(segment.index)) return 'other2';
                
                return selectedSegment === segment.index ? 'selected' : '';
            };

            const handleSegmentClick = (segment) => {
                setSelectedSegment(selectedSegment === segment.index ? null : segment.index);
            };

            const assignField = (field) => {
                if (selectedSegment === null) return;
                
                setFieldAssignments(prev => {
                    const newAssignments = {...prev};
                    
                    Object.keys(newAssignments).forEach(key => {
                        if (Array.isArray(newAssignments[key])) {
                            newAssignments[key] = newAssignments[key].filter(i => i !== selectedSegment);
                        } else if (newAssignments[key] === selectedSegment) {
                            newAssignments[key] = null;
                        }
                    });

                    if (Array.isArray(newAssignments[field])) {
                        newAssignments[field].push(selectedSegment);
                    } else {
                        newAssignments[field] = selectedSegment;
                    }

                    return newAssignments;
                });

                setSelectedSegment(null);
            };

            const getFieldDisplay = (field) => {
                if (Array.isArray(fieldAssignments[field])) {
                    if (fieldAssignments[field].length === 0) return "None";
                    return fieldAssignments[field]
                        .sort((a, b) => a - b)
                        .map(index => {
                            const segment = segments.find(s => s.index === index);
                            return segment ? segment.text : '';
                        })
                        .filter(text => text)
                        .join(" ");
                } else {
                    if (fieldAssignments[field] === null) return "None";
                    const segment = segments.find(s => s.index === fieldAssignments[field]);
                    return segment ? segment.text : "None";
                }
            };

            return (
                <div style={{ padding: '0 20px' }}>
                    <h3>Current Filename:</h3>
                    <div style={{ marginBottom: '20px', padding: '10px', backgroundColor: '#f5f5f5' }}>
                        {filename}
                    </div>

                    <h3>Segments:</h3>
                    <div className="instructions">
                        Click on a segment below, then click the corresponding button to identify what type of information it represents.
                        Click a segment again to unassign it.
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '20px' }}>
                        {segments.map((segment) => (
                            <button
                                key={segment.index}
                                onClick={() => handleSegmentClick(segment)}
                                className={`segment-btn ${getSegmentClass(segment)}`}
                                style={{ width: 'auto' }}
                            >
                                {segment.text}
                            </button>
                        ))}
                    </div>

                    <h3>Assign Selected Segment:</h3>
                    
                    {/* Publication Row */}
                    <div className="button-row">
                        <button onClick={() => assignField('publication')} className="segment-btn publication">Publication Name</button>
                        <button onClick={() => assignField('title')} className="segment-btn title">File/Article Title</button>
                        <button onClick={() => assignField('author')} className="segment-btn author">Author</button>
                    </div>
                    <div className="display-row">
                        <div className="display-field">{getFieldDisplay('publication')}</div>
                        <div className="display-field">{getFieldDisplay('title')}</div>
                        <div className="display-field">{getFieldDisplay('author')}</div>
                    </div>

                    {/* Date Row */}
                    <div className="button-row">
                        <button onClick={() => assignField('year')} className="segment-btn year">Year</button>
                        <button onClick={() => assignField('month')} className="segment-btn month">Month</button>
                        <button onClick={() => assignField('day')} className="segment-btn day">Day</button>
                    </div>
                    <div className="display-row">
                        <div className="display-field">{getFieldDisplay('year')}</div>
                        <div className="display-field">{getFieldDisplay('month')}</div>
                        <div className="display-field">{getFieldDisplay('day')}</div>
                    </div>

                    {/* Issue Row */}
                    <div className="button-row">
                        <button onClick={() => assignField('volume')} className="segment-btn volume">Volume #</button>
                        <button onClick={() => assignField('issue')} className="segment-btn issue">Issue #</button>
                        <button onClick={() => assignField('page')} className="segment-btn page">Page #</button>
                    </div>
                    <div className="display-row">
                        <div className="display-field">{getFieldDisplay('volume')}</div>
                        <div className="display-field">{getFieldDisplay('issue')}</div>
                        <div className="display-field">{getFieldDisplay('page')}</div>
                    </div>

                    {/* Other Row */}
                    <div className="button-row">
                        <button onClick={() => assignField('doi')} className="segment-btn doi">DOI</button>
                        <button onClick={() => assignField('other1')} className="segment-btn other1">Other 1</button>
                        <button onClick={() => assignField('other2')} className="segment-btn other2">Other 2</button>
                    </div>
                    <div className="display-row">
                        <div className="display-field">{getFieldDisplay('doi')}</div>
                        <div className="display-field">{getFieldDisplay('other1')}</div>
                        <div className="display-field">{getFieldDisplay('other2')}</div>
                    </div>

                    <div style={{ textAlign: 'center', marginTop: '20px' }}>
                        <button 
                            onClick={() => {
                                const match = filename.match(/[_\s-]+/);
                                const separator = match ? match[0] : '_';
                                
                                const pattern = {
                                    fieldAssignments,
                                    segments,
                                    separator: separator
                                };
                                
                                console.log('Save button clicked');
                                console.log('Pattern data:', pattern);
                                console.log('Bridge object:', window.bridge);
                                
                                if (window.bridge && typeof window.bridge.save_pattern === 'function') {
                                    console.log('Calling bridge.save_pattern');
                                    window.bridge.save_pattern(JSON.stringify(pattern));
                                } else {
                                    console.error('Bridge not properly initialized:', window.bridge);
                                }
                            }}
                            style={{
                                padding: '10px 20px',
                                backgroundColor: '#4CAF50',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '16px',
                                fontWeight: 'bold'
                            }}
                        >
                            Save Pattern Rule
                        </button>
                    </div>
                </div>
            );
        };

        ReactDOM.render(<FilenameParser />, document.getElementById('root'));
    </script>
</body>
</html>
'''

class Bridge(QObject):
    pattern_received = pyqtSignal(str)
    
    @pyqtSlot(str)
    def save_pattern(self, pattern):
        print("Bridge received pattern:", pattern)  # Debug print
        self.pattern_received.emit(pattern)

class FilenameParserWidget(QWidget):
    pattern_saved = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.web_view = QWebEngineView()
        
        # Create bridge and channel first
        page = self.web_view.page()
        self.channel = QWebChannel(page)
        self.bridge = Bridge()
        self.bridge.pattern_received.connect(self.handle_save_pattern)
        self.channel.registerObject('bridge', self.bridge)
        page.setWebChannel(self.channel)

        # Modify the HTML content to include bridge initialization
        html_content = get_html_content()
        bridge_setup = """
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        window.bridge = channel.objects.bridge;
                        console.log('Bridge initialized:', window.bridge);
                    });
                });
            </script>
        """
        
        # Insert bridge setup script just before closing head tag
        html_content = html_content.replace('</head>', f'{bridge_setup}</head>')
        
        self.web_view.setHtml(html_content)
        layout.addWidget(self.web_view)
        self.setLayout(layout)

    def handle_save_pattern(self, pattern_json):
        try:
            print("handle_save_pattern received:", pattern_json)  # Debug print
            pattern_data = json.loads(pattern_json)
            print("Parsed pattern data:", pattern_data)  # Debug print
            self.pattern_saved.emit(pattern_data)
        except Exception as e:
            print(f"Error in handle_save_pattern: {str(e)}")

    def update_filename(self, filename):
            script = f'window.updateFilename("{filename}");'
            self.web_view.page().runJavaScript(script)

    def _generate_format_description(self, pattern_data):
        """Generate a human-readable format description from the pattern."""
        assignments = pattern_data['fieldAssignments']
        segments = pattern_data['segments']
        
        format_parts = []
        for i in range(len(segments)):
            if any(i in assignments.get(field, []) for field in ['publication', 'title', 'author']):
                for field in ['publication', 'title', 'author']:
                    if i in assignments.get(field, []):
                        format_parts.append(field)
                        break
            elif i == assignments.get('year'):
                format_parts.append('YYYY')
            elif i == assignments.get('month'):
                format_parts.append('MM')
            elif i == assignments.get('day'):
                format_parts.append('DD')
            elif i == assignments.get('volume'):
                format_parts.append('VOL')
            elif i == assignments.get('issue'):
                format_parts.append('ISSUE')
            elif i == assignments.get('page'):
                format_parts.append('PAGE')
            elif any(i in assignments.get(field, []) for field in ['doi', 'other1', 'other2']):
                for field in ['doi', 'other1', 'other2']:
                    if i in assignments.get(field, []):
                        format_parts.append(field)
                        break
        
        return pattern_data['separator'].join(format_parts)

    def _generate_example(self, pattern_data):
        """Generate an example string based on the pattern."""
        return ' '.join([seg['text'] for seg in pattern_data['segments']])
    
    def clear_fields(self):
        """Clear all fields after successful save."""
        script = """
            if (window.clearFields) {
                window.clearFields();
            }
        """
        self.web_view.page().runJavaScript(script)    