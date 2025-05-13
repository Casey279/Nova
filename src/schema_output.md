# Nova Database Schema

**Database Path**: c:\AI\Nova\src\nova_database.db
**Size**: 0.61 MB

## Table of Contents

1. [Tables](#tables)
   - [BrainstormingSessions](#brainstormingsessions)
   - [Characters](#characters)
   - [Entities](#entities)
   - [EventCharacters](#eventcharacters)
   - [EventEntities](#evententities)
   - [EventLocations](#eventlocations)
   - [EventMetadata](#eventmetadata)
   - [Events](#events)
   - [FilenameParsingRules](#filenameparsingrules)
   - [LocationOccupations](#locationoccupations)
   - [Locations](#locations)
   - [PrimaryCharacters](#primarycharacters)
   - [QuaternaryCharacters](#quaternarycharacters)
   - [SecondaryCharacters](#secondarycharacters)
   - [Sources](#sources)
   - [TabEvents](#tabevents)
   - [TertiaryCharacters](#tertiarycharacters)
   - [TransientCharacters](#transientcharacters)
   - [TransientEntities](#transiententities)
   - [TransientEventCharacters](#transienteventcharacters)
   - [TransientEventEntities](#transientevententities)
   - [TransientEventLocations](#transienteventlocations)
   - [TransientEventMetadata](#transienteventmetadata)
   - [TransientEvents](#transientevents)
   - [TransientLocations](#transientlocations)
   - [TransientSources](#transientsources)
2. [Relationships](#relationships)
3. [Sample Queries](#sample-queries)
4. [Database Analysis](#database-analysis)

## Tables

### Project Tables

### Characters
**Row count:** 0

**Primary Key(s):** CharacterID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| CharacterID | INTEGER |  |  | ✓ |
| DisplayName | TEXT |  |  |  |
| FirstName | TEXT |  |  |  |
| LastName | TEXT |  |  |  |
| Aliases | TEXT |  |  |  |
| BirthDate | TEXT |  |  |  |
| DeathDate | TEXT |  |  |  |
| Height | TEXT |  |  |  |
| Weight | TEXT |  |  |  |
| Eyes | TEXT |  |  |  |
| Hair | TEXT |  |  |  |
| Occupation | TEXT |  |  |  |
| Family | TEXT |  |  |  |
| Affiliations | TEXT |  |  |  |
| PersonalityTraits | TEXT |  |  |  |
| BackgroundSummary | TEXT |  |  |  |
| Gender | TEXT |  |  |  |
| MyersBriggs | TEXT |  |  |  |
| Enneagram | TEXT |  |  |  |
| ClifftonStrengths | TEXT |  |  |  |
| ImagePath | TEXT |  |  |  |
| FindAGrave | TEXT |  |  |  |
| Reviewed | INTEGER |  | 0 |  |
| Prefix | TEXT |  |  |  |
| MiddleName | TEXT |  |  |  |
| Suffix | TEXT |  |  |  |

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_Characters_1 (DisplayName)

### Entities
**Row count:** 0

**Primary Key(s):** EntityID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EntityID | INTEGER |  |  | ✓ |
| DisplayName | TEXT |  |  |  |
| Name | TEXT |  |  |  |
| Aliases | TEXT |  |  |  |
| Type | TEXT |  |  |  |
| Description | TEXT |  |  |  |
| EstablishedDate | TEXT |  |  |  |
| Affiliation | TEXT |  |  |  |
| Summary | TEXT |  |  |  |
| ImagePath | TEXT |  |  |  |
| KnownMembers | TEXT |  | '' |  |

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_Entities_1 (DisplayName)

### EventCharacters
**Row count:** 0

**Primary Key(s):** EventID, CharacterID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| CharacterID | INTEGER |  |  | ✓ |

**Foreign Keys:**
- CharacterID → Characters(CharacterID)
- EventID → Events(EventID)

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_EventCharacters_1 (EventID, CharacterID)

### EventEntities
**Row count:** 0

**Primary Key(s):** EventID, EntityID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| EntityID | INTEGER |  |  | ✓ |

**Foreign Keys:**
- EntityID → Entities(EntityID)
- EventID → Events(EventID)

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_EventEntities_1 (EventID, EntityID)

### EventLocations
**Row count:** 0

**Primary Key(s):** EventID, LocationID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| LocationID | INTEGER |  |  | ✓ |

**Foreign Keys:**
- LocationID → Locations(LocationID)
- EventID → Events(EventID)

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_EventLocations_1 (EventID, LocationID)

### EventMetadata
**Row count:** 0

**Primary Key(s):** MetadataID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| MetadataID | INTEGER |  |  | ✓ |
| EventID | INTEGER |  |  |  |
| Key | TEXT |  |  |  |
| Value | TEXT |  |  |  |

**Foreign Keys:**
- EventID → Events(EventID)

### Events
**Row count:** 0

**Primary Key(s):** EventID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| EventDate | TEXT |  |  |  |
| EventTitle | TEXT |  |  |  |
| EventText | TEXT |  |  |  |
| SourceType | TEXT |  |  |  |
| SourceName | TEXT |  |  |  |
| Filename | TEXT |  |  |  |
| FilePath | TEXT |  |  |  |
| PublicationDate | TEXT |  |  |  |
| SourceID | INTEGER |  |  |  |
| Status | TEXT |  | 'active' |  |
| QualityScore | INTEGER |  |  |  |
| PageNumber | TEXT |  |  |  |

### LocationOccupations
**Row count:** 0

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| LocationID | INTEGER |  |  |  |
| CharacterID | INTEGER |  |  |  |
| RoleType | TEXT |  |  |  |
| StartDate | TEXT |  |  |  |
| EndDate | TEXT |  |  |  |
| Notes | TEXT |  |  |  |

**Foreign Keys:**
- CharacterID → Characters(CharacterID)
- LocationID → Locations(LocationID)

### Locations
**Row count:** 0

**Primary Key(s):** LocationID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| LocationID | INTEGER |  |  | ✓ |
| DisplayName | TEXT |  |  |  |
| LocationName | TEXT |  |  |  |
| Aliases | TEXT |  |  |  |
| Address | TEXT |  |  |  |
| LocationType | TEXT |  |  |  |
| YearBuilt | TEXT |  |  |  |
| Description | TEXT |  |  |  |
| Owners | TEXT |  |  |  |
| Managers | TEXT |  |  |  |
| Employees | TEXT |  |  |  |
| Summary | TEXT |  |  |  |
| ImagePath | TEXT |  |  |  |
| ReviewStatus | TEXT |  | 'needs_review' |  |

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_Locations_1 (DisplayName)

### Sources
**Row count:** 0

**Primary Key(s):** SourceID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| SourceID | INTEGER |  |  | ✓ |
| SourceName | TEXT | ✓ |  |  |
| SourceType | TEXT |  |  |  |
| Abbreviation | TEXT |  |  |  |
| Publisher | TEXT |  |  |  |
| Location | TEXT |  |  |  |
| EstablishedDate | TEXT |  |  |  |
| DiscontinuedDate | TEXT |  |  |  |
| ImagePath | TEXT |  |  |  |
| SourceCode | TEXT |  |  |  |
| Aliases | TEXT |  |  |  |
| ReviewStatus | TEXT |  | 'needs_review' |  |
| PoliticalAffiliations | TEXT |  |  |  |
| Summary | TEXT |  |  |  |

### Application Tables

### BrainstormingSessions
**Row count:** 0

**Primary Key(s):** SessionID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| SessionID | INTEGER |  |  | ✓ |
| SessionName | TEXT |  |  |  |
| CreatedDate | TEXT |  |  |  |
| LastModified | TEXT |  |  |  |
| Scope | TEXT |  |  |  |
| StartingPoint | TEXT |  |  |  |
| EndingPoint | TEXT |  |  |  |
| DevelopmentNotes | TEXT |  |  |  |
| AIInteractions | TEXT |  |  |  |
| Status | TEXT |  |  |  |

### FilenameParsingRules
**Row count:** 0

**Primary Key(s):** id

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| id | INTEGER |  |  | ✓ |
| source_name | TEXT | ✓ |  |  |
| pattern | TEXT | ✓ |  |  |
| format_description | TEXT | ✓ |  |  |
| example | TEXT | ✓ |  |  |
| is_custom | BOOLEAN |  | 0 |  |

### PrimaryCharacters
**Row count:** 0

**Primary Key(s):** CharacterID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| CharacterID | INTEGER |  |  | ✓ |

**Foreign Keys:**
- CharacterID → Characters(CharacterID)

### QuaternaryCharacters
**Row count:** 0

**Primary Key(s):** CharacterID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| CharacterID | INTEGER |  |  | ✓ |

**Foreign Keys:**
- CharacterID → Characters(CharacterID)

### SecondaryCharacters
**Row count:** 0

**Primary Key(s):** CharacterID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| CharacterID | INTEGER |  |  | ✓ |

**Foreign Keys:**
- CharacterID → Characters(CharacterID)

### TabEvents
**Row count:** 0

**Primary Key(s):** EventID, CharacterID, LocationID, EntityID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| CharacterID | INTEGER |  |  | ✓ |
| LocationID | INTEGER |  |  | ✓ |
| EntityID | INTEGER |  |  | ✓ |

**Foreign Keys:**
- EntityID → Entities(EntityID)
- LocationID → Locations(LocationID)
- CharacterID → Characters(CharacterID)
- EventID → Events(EventID)

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_TabEvents_1 (EventID, CharacterID, LocationID, EntityID)

### TertiaryCharacters
**Row count:** 0

**Primary Key(s):** CharacterID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| CharacterID | INTEGER |  |  | ✓ |

**Foreign Keys:**
- CharacterID → Characters(CharacterID)

### TransientCharacters
**Row count:** 0

**Primary Key(s):** CharacterID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| CharacterID | INTEGER |  |  | ✓ |
| DisplayName | TEXT |  |  |  |
| FirstName | TEXT |  |  |  |
| LastName | TEXT |  |  |  |
| Aliases | TEXT |  |  |  |
| BirthDate | TEXT |  |  |  |
| DeathDate | TEXT |  |  |  |
| Height | TEXT |  |  |  |
| Weight | TEXT |  |  |  |
| Eyes | TEXT |  |  |  |
| Hair | TEXT |  |  |  |
| Occupation | TEXT |  |  |  |
| Family | TEXT |  |  |  |
| Affiliations | TEXT |  |  |  |
| PersonalityTraits | TEXT |  |  |  |
| BackgroundSummary | TEXT |  |  |  |
| Gender | TEXT |  |  |  |
| MyersBriggs | TEXT |  |  |  |
| Enneagram | TEXT |  |  |  |
| ClifftonStrengths | TEXT |  |  |  |
| ImagePath | TEXT |  |  |  |
| FindAGrave | TEXT |  |  |  |
| Reviewed | INTEGER |  |  |  |
| Classification | TEXT |  |  |  |

### TransientEntities
**Row count:** 0

**Primary Key(s):** EntityID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EntityID | INTEGER |  |  | ✓ |
| DisplayName | TEXT |  |  |  |
| Name | TEXT |  |  |  |
| Aliases | TEXT |  |  |  |
| Type | TEXT |  |  |  |
| Description | TEXT |  |  |  |
| EstablishedDate | TEXT |  |  |  |
| Affiliation | TEXT |  |  |  |
| Summary | TEXT |  |  |  |
| ImagePath | TEXT |  |  |  |
| KnownMembers | TEXT |  |  |  |

### TransientEventCharacters
**Row count:** 0

**Primary Key(s):** EventID, CharacterID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| CharacterID | INTEGER |  |  | ✓ |

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_TransientEventCharacters_1 (EventID, CharacterID)

### TransientEventEntities
**Row count:** 0

**Primary Key(s):** EventID, EntityID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| EntityID | INTEGER |  |  | ✓ |

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_TransientEventEntities_1 (EventID, EntityID)

### TransientEventLocations
**Row count:** 0

**Primary Key(s):** EventID, LocationID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| LocationID | INTEGER |  |  | ✓ |

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_TransientEventLocations_1 (EventID, LocationID)

### TransientEventMetadata
**Row count:** 0

**Primary Key(s):** EventID, MetadataKey

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| MetadataKey | TEXT |  |  | ✓ |
| MetadataValue | TEXT |  |  |  |

**Indexes:**
- UNIQUE INDEX sqlite_autoindex_TransientEventMetadata_1 (EventID, MetadataKey)

### TransientEvents
**Row count:** 0

**Primary Key(s):** EventID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| EventID | INTEGER |  |  | ✓ |
| EventDate | TEXT |  |  |  |
| PublicationDate | TEXT |  |  |  |
| EventTitle | TEXT |  |  |  |
| EventText | TEXT |  |  |  |
| SourceType | TEXT |  |  |  |
| SourceName | TEXT |  |  |  |
| Filename | TEXT |  |  |  |
| FilePath | TEXT |  |  |  |
| SourceID | INTEGER |  |  |  |
| QualityScore | INTEGER |  |  |  |

**Foreign Keys:**
- SourceID → TransientSources(SourceID)

### TransientLocations
**Row count:** 0

**Primary Key(s):** LocationID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| LocationID | INTEGER |  |  | ✓ |
| DisplayName | TEXT |  |  |  |
| LocationName | TEXT |  |  |  |
| Aliases | TEXT |  |  |  |
| Address | TEXT |  |  |  |
| LocationType | TEXT |  |  |  |
| YearBuilt | TEXT |  |  |  |
| Description | TEXT |  |  |  |
| Owners | TEXT |  |  |  |
| Managers | TEXT |  |  |  |
| Employees | TEXT |  |  |  |
| Summary | TEXT |  |  |  |
| ImagePath | TEXT |  |  |  |
| ReviewStatus | TEXT |  |  |  |

### TransientSources
**Row count:** 0

**Primary Key(s):** SourceID

| Column | Type | NOT NULL | Default | Primary Key |
|--------|------|----------|---------|-------------|
| SourceID | INTEGER |  |  | ✓ |
| SourceName | TEXT |  |  |  |
| SourceType | TEXT |  |  |  |
| Abbreviation | TEXT |  |  |  |
| Publisher | TEXT |  |  |  |
| Location | TEXT |  |  |  |
| EstablishedDate | TEXT |  |  |  |
| DiscontinuedDate | TEXT |  |  |  |
| ImagePath | TEXT |  |  |  |
| SourceCode | TEXT |  |  |  |
| Aliases | TEXT |  |  |  |
| ReviewStatus | TEXT |  |  |  |
| PoliticalAffiliations | TEXT |  |  |  |
| Summary | TEXT |  |  |  |

## Relationships

| From Table | From Column | Relationship | To Table | To Column |
|------------|-------------|--------------|----------|-----------|
| EventCharacters | CharacterID | M:N | Characters | CharacterID |
| EventCharacters | EventID | M:N | Events | EventID |
| EventLocations | LocationID | M:N | Locations | LocationID |
| EventLocations | EventID | M:N | Events | EventID |
| EventEntities | EntityID | M:N | Entities | EntityID |
| EventEntities | EventID | M:N | Events | EventID |
| PrimaryCharacters | CharacterID | 1:N | Characters | CharacterID |
| SecondaryCharacters | CharacterID | 1:N | Characters | CharacterID |
| TertiaryCharacters | CharacterID | 1:N | Characters | CharacterID |
| QuaternaryCharacters | CharacterID | 1:N | Characters | CharacterID |
| TabEvents | EntityID | 1:N | Entities | EntityID |
| TabEvents | LocationID | 1:N | Locations | LocationID |
| TabEvents | CharacterID | 1:N | Characters | CharacterID |
| TabEvents | EventID | 1:N | Events | EventID |
| EventMetadata | EventID | 1:N | Events | EventID |
| LocationOccupations | CharacterID | 1:N | Characters | CharacterID |
| LocationOccupations | LocationID | 1:N | Locations | LocationID |
| TransientEvents | SourceID | 1:N | TransientSources | SourceID |

## Sample Queries

### Events Queries

#### Get All Events
```sql
SELECT EventID, EventDate, PublicationDate, EventTitle, QualityScore 
                    FROM Events
                    ORDER BY PublicationDate DESC
```

#### Get Event By Id
```sql
SELECT EventDate, PublicationDate, EventTitle, EventText, SourceType, SourceName, QualityScore
                    FROM Events 
                    WHERE EventID = ?
```

#### Get Event Associations
```sql
-- Characters associated with an event
                    SELECT Characters.DisplayName
                    FROM Characters
                    JOIN EventCharacters ON Characters.CharacterID = EventCharacters.CharacterID
                    WHERE EventCharacters.EventID = ?
                    
                    -- Locations associated with an event
                    SELECT Locations.LocationName
                    FROM Locations
                    JOIN EventLocations ON Locations.LocationID = EventLocations.LocationID
                    WHERE EventLocations.EventID = ?
                    
                    -- Entities associated with an event
                    SELECT Entities.Name
                    FROM Entities
                    JOIN EventEntities ON Entities.EntityID = EventEntities.EntityID
                    WHERE EventEntities.EventID = ?
```

### Characters Queries

#### Get Articles By Character
```sql
SELECT e.PublicationDate, e.EventTitle, e.EventID, e.EventText
                    FROM Events e
                    JOIN EventCharacters ec ON e.EventID = ec.EventID
                    WHERE ec.CharacterID = ? AND e.Status = 'active'
                    ORDER BY e.PublicationDate DESC
```

#### Get Character By Id
```sql
SELECT * FROM Characters WHERE CharacterID = ?
```

#### Get Character Occupations
```sql
SELECT l.DisplayName as location_name, lo.RoleType, 
                        lo.StartDate, lo.EndDate
                    FROM LocationOccupations lo
                    JOIN Locations l ON lo.LocationID = l.LocationID
                    WHERE lo.CharacterID = ?
                    ORDER BY lo.StartDate
```

### Locations Queries

#### Get Articles By Location
```sql
SELECT e.PublicationDate, e.EventTitle, e.EventID, e.EventText
                    FROM Events e
                    JOIN EventLocations ec ON e.EventID = ec.EventID
                    WHERE ec.LocationID = ? AND e.Status = 'active'
                    ORDER BY e.PublicationDate DESC
```

#### Get Location Occupants
```sql
SELECT c.DisplayName as character_name, lo.RoleType,
                        lo.StartDate, lo.EndDate
                    FROM LocationOccupations lo
                    JOIN Characters c ON lo.CharacterID = c.CharacterID
                    WHERE lo.LocationID = ?
                    ORDER BY lo.RoleType, lo.StartDate
```

### Entities Queries

#### Get Articles By Entity
```sql
SELECT e.PublicationDate, e.EventTitle, e.EventID, e.EventText
                    FROM Events e
                    JOIN EventEntities ec ON e.EventID = ec.EventID
                    WHERE ec.EntityID = ? AND e.Status = 'active'
                    ORDER BY e.PublicationDate DESC
```

#### Update Known Members
```sql
-- First get the entity name
                    SELECT DisplayName FROM Entities WHERE EntityID = ?
                    
                    -- Find all characters with this entity in their Affiliations
                    SELECT DisplayName FROM Characters WHERE Affiliations LIKE ?
                    
                    -- Update the KnownMembers field
                    UPDATE Entities SET KnownMembers = ? WHERE EntityID = ?
```

## Database Analysis

### Project Separation
The Nova database does not implement explicit project separation through schemas or prefixes. 
Instead, it uses a single database with all tables. Projects appear to be implicitly defined 
by the content of the Events, Characters, Locations, and Entities tables, possibly filtered 
by date ranges or other attributes.

The database follows a relational model with junction tables (EventCharacters, EventLocations, 
EventEntities) implementing many-to-many relationships between primary entities. This allows 
building complex narratives that span multiple entities.

### Core Entities
The database is organized around these core entities:
1. Events - Newspaper articles or other historical events with dates and text content
2. Characters - Historical individuals with biographical information
3. Locations - Physical places with addresses and descriptions
4. Entities - Organizations or groups with establishment dates and affiliations
5. Sources - Newspapers or other publication sources of events

Each of these entities has relationships with the others, primarily through the Events table
which acts as a hub connecting Characters, Locations, and Entities together.

### Temporal Model
The database includes various date fields (EventDate, PublicationDate, BirthDate, DeathDate, 
EstablishedDate, StartDate, EndDate) that enable temporal analysis and chronological ordering 
of records. This suggests the database is designed for historical research and narrative 
construction across time periods.

LocationOccupations is especially interesting as it tracks characters' relationships with
locations over time, including role types and date ranges, enabling temporal analysis of
character movements and occupations.
