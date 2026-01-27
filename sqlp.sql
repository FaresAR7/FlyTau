DROP DATABASE IF EXISTS FlyTau;
CREATE DATABASE FlyTau;
USE FlyTau;

-- ==========================================
-- 1. STAFF TABLES
-- ==========================================

CREATE TABLE Managers (
    EmployeeID INT PRIMARY KEY,
    FirstNameHebrew VARCHAR(50) NOT NULL,
    LastNameHebrew VARCHAR(50) NOT NULL,
    Phone VARCHAR(20),
    StartDate DATE,
    City VARCHAR(50),
    Street VARCHAR(50),
    HouseNum INT,
    Password VARCHAR(255) NOT NULL
);

CREATE TABLE Pilots (
    EmployeeID INT PRIMARY KEY,
    FirstNameHebrew VARCHAR(50) NOT NULL,
    LastNameHebrew VARCHAR(50) NOT NULL,
    Phone VARCHAR(20),
    StartDate DATE,
    City VARCHAR(50),
    Street VARCHAR(50),
    HouseNum INT,
    IsLongHaulQualified BOOLEAN DEFAULT FALSE
);

CREATE TABLE FlightAttendants (
    EmployeeID INT PRIMARY KEY,
    FirstNameHebrew VARCHAR(50) NOT NULL,
    LastNameHebrew VARCHAR(50) NOT NULL,
    Phone VARCHAR(20),
    StartDate DATE,
    City VARCHAR(50),
    Street VARCHAR(50),
    HouseNum INT,
    IsLongHaulQualified BOOLEAN DEFAULT FALSE
);

-- ==========================================
-- 2. CUSTOMER TABLES (Separate, no parent)
-- ==========================================

CREATE TABLE GuestCustomers (
    Email VARCHAR(100) PRIMARY KEY,
    FirstlNameEnglish VARCHAR(100) NOT NULL,
    LastlNameEnglish VARCHAR(100) NOT NULL
);

CREATE TABLE RegisteredCustomers (
    Email VARCHAR(100) PRIMARY KEY,
    FirstlNameEnglish VARCHAR(100),
    LastlNameEnglish VARCHAR(100),
    Password VARCHAR(255) NOT NULL,
    PassportNum VARCHAR(20),
    BirthDate DATE,
    RegistrationDate DATE
);

-- ==========================================
-- 3. PHONE TABLES 
-- ==========================================

CREATE TABLE GuestPhones (
    Email VARCHAR(100),
    PhoneNumber VARCHAR(20),
    PRIMARY KEY (Email, PhoneNumber),
    FOREIGN KEY (Email) REFERENCES GuestCustomers(Email) ON DELETE CASCADE
);

CREATE TABLE RegisteredPhones (
    Email VARCHAR(100),
    PhoneNumber VARCHAR(20),
    PRIMARY KEY (Email, PhoneNumber),
    FOREIGN KEY (Email) REFERENCES RegisteredCustomers(Email) ON DELETE CASCADE
);

-- ==========================================
-- 4. AIRCRAFT & FLIGHTS
-- ==========================================

CREATE TABLE Aircrafts (
    TailNum VARCHAR(20) PRIMARY KEY,
    Manufacturer VARCHAR(50),
    Size ENUM('Small', 'Large') NOT NULL,
    PurchaseDate DATE
);

CREATE TABLE AircraftLayout (
    TailNum VARCHAR(20),
    ClassType ENUM('Economy', 'Business') NOT NULL,
    NumRows INT NOT NULL,
    NumCols INT NOT NULL,
    PRIMARY KEY (TailNum, ClassType),
    FOREIGN KEY (TailNum) REFERENCES Aircrafts(TailNum) ON DELETE CASCADE
);

CREATE TABLE Routes (
    RouteID INT AUTO_INCREMENT PRIMARY KEY,
    SourceAirport VARCHAR(30) NOT NULL,
    DestAirport VARCHAR(30) NOT NULL,
    DurationMinutes INT NOT NULL,
    UNIQUE (SourceAirport, DestAirport)
);

CREATE TABLE Flights (
    FlightNum VARCHAR(20) PRIMARY KEY,
    RouteID INT NOT NULL,
    TailNum VARCHAR(20) NOT NULL,
    DepartureTime TIME NOT NULL,
    DepartureDate DATE NOT NULL,
    StatusF ENUM('Active', 'Full', 'Arrived', 'Canceled'),

    FOREIGN KEY (RouteID) REFERENCES Routes(RouteID),
    FOREIGN KEY (TailNum) REFERENCES Aircrafts(TailNum)
);

CREATE TABLE FlightPricing (
    FlightNum VARCHAR(20),
    ClassType ENUM('Economy', 'Business'),
    Price DECIMAL(10, 2) NOT NULL,

    PRIMARY KEY (FlightNum, ClassType),
    FOREIGN KEY (FlightNum) REFERENCES Flights(FlightNum) ON DELETE CASCADE
);

-- ==========================================
-- 5. CREW ASSIGNMENTS 
-- ==========================================

-- Table specifically for Pilots on a flight
CREATE TABLE CrewPilots (
    FlightNum VARCHAR(20),
    PilotID INT,
    PRIMARY KEY (FlightNum, PilotID),
    FOREIGN KEY (FlightNum) REFERENCES Flights(FlightNum) ON DELETE CASCADE,
    FOREIGN KEY (PilotID) REFERENCES Pilots(EmployeeID) ON DELETE CASCADE
);

-- Table specifically for Attendants on a flight
CREATE TABLE CrewAttendants (
    FlightNum VARCHAR(20),
    AttendantID INT,
    PRIMARY KEY (FlightNum, AttendantID),
    FOREIGN KEY (FlightNum) REFERENCES Flights(FlightNum) ON DELETE CASCADE,
    FOREIGN KEY (AttendantID) REFERENCES FlightAttendants(EmployeeID) ON DELETE CASCADE
);

-- ==========================================
-- 6. ORDERS & TICKETS 
-- ==========================================

CREATE TABLE Orders (
    OrderID INT AUTO_INCREMENT PRIMARY KEY,

    -- Two columns: one for Guest, one for Registered
    GuestEmail VARCHAR(100),
    RegisteredEmail VARCHAR(100),

    OrderDate DATETIME ,
    TotalPrice DECIMAL(10, 2) DEFAULT 0,
    OrderStatus ENUM('Paid', 'Active', 'CustCancelled', 'SysCancelled') ,

    -- Foreign Keys ensure the email actually exists in the specific table
    FOREIGN KEY (GuestEmail) REFERENCES GuestCustomers(Email) ON DELETE CASCADE,
    FOREIGN KEY (RegisteredEmail) REFERENCES RegisteredCustomers(Email) ON DELETE CASCADE,
    CHECK ((GuestEmail IS NOT NULL AND RegisteredEmail IS NULL) OR (GuestEmail IS NULL AND RegisteredEmail IS NOT NULL))
);

CREATE TABLE Tickets (
    TicketID INT AUTO_INCREMENT PRIMARY KEY,
    OrderID INT NOT NULL,
    FlightNum VARCHAR(20) NOT NULL,
    PassengerName VARCHAR(100),
    ClassType ENUM('Economy', 'Business') NOT NULL,
    SeatRow INT,
    SeatCol VARCHAR(5),

    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID) ON DELETE CASCADE,
    FOREIGN KEY (FlightNum) REFERENCES Flights(FlightNum),
    UNIQUE (FlightNum, SeatRow, SeatCol)
);

#DATA
USE FlyTau;

SET FOREIGN_KEY_CHECKS = 0;

-- =====================================================
-- 1. MANAGERS (Hebrew names, NOT customers)
-- =====================================================
INSERT INTO Managers VALUES
(9001,'דן','לוי','0501111111','2016-01-01','תל אביב','בן גוריון',1,'admin1'),
(9002,'נועה','כהן','0502222222','2017-01-01','חיפה','הרצל',2,'admin2'),
(9003,'פארס','רחאל','0503333333','2018-01-01','ירושלים','יפו',3,'admin3'),
(9004,'מאיה','דוד','0504444444','2019-01-01','באר שבע','רגר',4,'admin4');

-- =====================================================
-- 2. PILOTS (half long-haul)
-- =====================================================
INSERT INTO Pilots VALUES
(1001,'יואב','לוי','0520000001','2016-01-01','תל אביב','אבן גבירול',1,1),
(1002,'רון','כהן','0520000002','2016-01-01','תל אביב','אבן גבירול',2,1),
(1003,'דני','פרידמן','0520000003','2016-01-01','תל אביב','אבן גבירול',3,1),
(1004,'גיל','שחר','0520000004','2017-01-01','תל אביב','אבן גבירול',4,0),
(1005,'עומר','ברק','0520000005','2017-01-01','תל אביב','אבן גבירול',5,0),
(1006,'איתי','רוזן','0520000006','2017-01-01','תל אביב','אבן גבירול',6,0);

-- =====================================================
-- 3. FLIGHT ATTENDANTS (half long-haul)
-- =====================================================
INSERT INTO FlightAttendants VALUES
(2001,'שרה','כהן','0530000001','2016-01-01','תל אביב','דיזנגוף',1,1),
(2002,'מיכל','לוי','0530000002','2016-01-01','תל אביב','דיזנגוף',2,1),
(2003,'נועה','בר','0530000003','2016-01-01','תל אביב','דיזנגוף',3,1),
(2004,'דנה','שחר','0530000004','2017-01-01','תל אביב','דיזנגוף',4,0),
(2005,'לירון','רז','0530000005','2017-01-01','תל אביב','דיזנגוף',5,0),
(2006,'אור','ממן','0530000006','2017-01-01','תל אביב','דיזנגוף',6,0),
(2007,'טלי','חי','0530000405','2017-01-01','תל אביב','דיזנגוף',5,0),
(2008,'קירל','חי','0530007005','2017-01-01','תל אביב','דיזנגוף',5,0);

-- =====================================================
-- 4. CUSTOMERS (English names only)
-- =====================================================
INSERT INTO GuestCustomers VALUES
('guest1@mail.com','John','Smith'),
('guest2@mail.com','Anna','Brown'),
('guest3@mail.com','Tom','White');

INSERT INTO RegisteredCustomers VALUES
('user1@mail.com','David','Green','pass1','P111','1990-01-01','2023-01-01'),
('user2@mail.com','Emma','Black','pass2','P222','1992-02-02','2023-01-01'),
('user3@mail.com','Liam','Gray','pass3','P333','1994-03-03','2023-01-01');

INSERT INTO GuestPhones VALUES
('guest1@mail.com','0541111111'),
('guest2@mail.com','0542222222'),
('guest3@mail.com','0543333333');

INSERT INTO RegisteredPhones VALUES
('user1@mail.com','0551111111'),
('user2@mail.com','0552222222'),
('user3@mail.com','0553333333');

-- =====================================================
-- 5. AIRCRAFTS + LAYOUT
-- =====================================================
INSERT INTO Aircrafts VALUES
('TA-L01','Boeing','Large','2015-01-01'),
('TA-L02','Airbus','Large','2016-01-01'),
('TA-S01','Dassault','Small','2019-01-01'),
('TA-S02','Dassault','Small','2020-01-01');

INSERT INTO AircraftLayout VALUES
('TA-L01','Economy',30,6),
('TA-L01','Business',10,4),
('TA-L02','Economy',28,6),
('TA-L02','Business',8,4),
('TA-S01','Economy',20,4),
('TA-S02','Economy',18,4);

-- =====================================================
-- 6. ROUTES
-- =====================================================
INSERT INTO Routes (SourceAirport,DestAirport,DurationMinutes) VALUES
('TLV','ATH',120),
('ATH','TLV',120),
('TLV','ROM',150),
('ROM','TLV',150),
('TLV','NYC',600),
('NYC','TLV',600);

-- =====================================================
-- 7. FLIGHTS (ALL STATUSES)
-- =====================================================
INSERT INTO Flights VALUES
-- small aircraft (short only)
('FS001',1,'TA-S01','08:00','2026-03-01','Active'),
('FS002',2,'TA-S01','14:00','2026-01-01','Arrived'),
('FS003',3,'TA-S02','09:00','2026-03-02','Full'),

-- large short
('FL001',1,'TA-L01','10:00','2026-03-03','Active'),
('FL002',2,'TA-L01','17:00','2026-03-03','Canceled'),

-- large long
('FL003',5,'TA-L02','22:00','2026-03-04','Full'),
('FL004',6,'TA-L02','09:00','2026-01-05','Arrived');

-- =====================================================
-- 8. FLIGHT PRICING
-- =====================================================
INSERT INTO FlightPricing VALUES
('FS001','Economy',120),
('FS002','Economy',120),
('FS003','Economy',140),

('FL001','Economy',150),
('FL001','Business',300),

('FL003','Economy',900),
('FL003','Business',1600),

('FL004','Economy',900),
('FL004','Business',1600);

-- =====================================================
-- 9. CREW ASSIGNMENT 
-- =====================================================
-- short chain
INSERT INTO CrewPilots VALUES
('FS001',1004),('FS001',1005),
('FS002',1004),('FS002',1005);

INSERT INTO CrewAttendants VALUES
('FS001',2004),('FS001',2005),('FS001',2006),
('FS002',2004),('FS002',2005),('FS002',2006);

-- long chain
INSERT INTO CrewPilots VALUES
('FL003',1001),('FL003',1002),('FL003',1003),
('FL004',1001),('FL004',1002),('FL004',1003);

INSERT INTO CrewAttendants VALUES
('FL003',2001),('FL003',2002),('FL003',2003),
('FL003',2004),('FL003',2005),('FL003',2006),
('FL004',2001),('FL004',2002),('FL004',2003),
('FL004',2004),('FL004',2005),('FL004',2006);

-- =====================================================
-- 10. ORDERS
-- =====================================================
INSERT INTO Orders VALUES
(1,'guest1@mail.com',NULL,NOW(),280,'Paid'),
(2,NULL,'user1@mail.com',NOW(),3200,'Paid'),
(3,'guest2@mail.com',NULL,NOW(),0,'SysCancelled'),
(4,NULL,'user2@mail.com',NOW(),0,'SysCancelled');

-- =====================================================
-- 11. TICKETS (FULL + CANCELED)
-- =====================================================
INSERT INTO Tickets VALUES
(NULL,1,'FS003','John Smith','Economy',1,'A'),
(NULL,1,'FS003','Anna Brown','Economy',1,'B'),
(NULL,2,'FL003','David Green','Business',1,'A'),
(NULL,2,'FL003','David Green','Business',1,'B');

SET FOREIGN_KEY_CHECKS = 1;

/* =========================================================
   ADD MORE DATA 
   ========================================================= 

#USE FlyTau;

-- =====================================================
-- A) ADD MORE PILOTS
--    (add both long-haul qualified and non-qualified)
-- =====================================================
INSERT INTO Pilots VALUES
(1007,'אלון','כהן','0520000007','2018-02-01','תל אביב','אבן גבירול',7,1),
(1008,'עידן','לוי','0520000008','2018-03-01','חיפה','הרצל',8,1),
(1009,'מתן','פרץ','0520000009','2019-01-01','ירושלים','יפו',9,1),
(1010,'שחר','רון','0520000010','2019-05-01','באר שבע','רגר',10,0),
(1011,'אורי','דוד','0520000011','2020-01-01','תל אביב','דיזנגוף',11,0),
(1012,'ליאור','ברק','0520000012','2020-06-01','חיפה','כרמל',12,0);

-- =====================================================
-- B) ADD MORE FLIGHT ATTENDANTS
-- =====================================================
INSERT INTO FlightAttendants VALUES
-- add long-haul qualified attendants
(2009,'יעל','כהן','0530000009','2018-02-01','תל אביב','דיזנגוף',9,1),
(2010,'מאי','לוי','0530000010','2018-03-01','חיפה','הרצל',10,1),
(2011,'שני','בר','0530000011','2019-01-01','ירושלים','יפו',11,1),
(2012,'רעות','דוד','0530000012','2019-05-01','באר שבע','רגר',12,1),

-- add non-qualified attendants (for short flights)
(2013,'עדי','שחר','0530000013','2020-01-01','תל אביב','דיזנגוף',13,0),
(2014,'ניב','רז','0530000014','2020-06-01','חיפה','כרמל',14,0),
(2015,'אושר','ממן','0530000015','2021-01-01','ירושלים','יפו',15,0),
(2016,'גל','חי','0530000016','2021-05-01','תל אביב','דיזנגוף',16,0);

-- =====================================================
-- C) ADD MORE ROUTES (short + long)
--    RouteID is AUTO_INCREMENT, so we use subqueries later.
-- =====================================================
INSERT INTO Routes (SourceAirport,DestAirport,DurationMinutes) VALUES
('ROM','ATH',110),     -- short
('ATH','ROM',110),     -- short
('NYC','ROM',540),     -- long
('ROM','NYC',540);     -- long

-- =====================================================
-- D) ADD MORE FLIGHTS (many scenarios)
--    - small aircraft => only short routes
--    - large aircraft => short + long routes
--    - mixed statuses
-- =====================================================

/* ---- SMALL aircraft flights (short only) ---- */
INSERT INTO Flights VALUES
('FS010', (SELECT RouteID FROM Routes WHERE SourceAirport='TLV' AND DestAirport='ATH' LIMIT 1), 'TA-S01', '08:30', '2026-03-05', 'Active'),
('FS011', (SELECT RouteID FROM Routes WHERE SourceAirport='ATH' AND DestAirport='TLV' LIMIT 1), 'TA-S01', '13:30', '2026-03-05', 'Full'),
('FS012', (SELECT RouteID FROM Routes WHERE SourceAirport='TLV' AND DestAirport='ROM' LIMIT 1), 'TA-S02', '09:15', '2026-03-06', 'Arrived'),
('FS013', (SELECT RouteID FROM Routes WHERE SourceAirport='ROM' AND DestAirport='TLV' LIMIT 1), 'TA-S02', '15:10', '2026-03-06', 'Canceled'),
('FS014', (SELECT RouteID FROM Routes WHERE SourceAirport='ROM' AND DestAirport='ATH' LIMIT 1), 'TA-S01', '11:00', '2026-03-07', 'Active'),
('FS015', (SELECT RouteID FROM Routes WHERE SourceAirport='ATH' AND DestAirport='ROM' LIMIT 1), 'TA-S01', '18:00', '2026-03-07', 'Arrived');

/* ---- LARGE aircraft flights (short) ---- */
INSERT INTO Flights VALUES
('FL010', (SELECT RouteID FROM Routes WHERE SourceAirport='TLV' AND DestAirport='ROM' LIMIT 1), 'TA-L01', '07:20', '2026-03-05', 'Active'),
('FL011', (SELECT RouteID FROM Routes WHERE SourceAirport='ROM' AND DestAirport='TLV' LIMIT 1), 'TA-L01', '12:40', '2026-03-05', 'Full'),
('FL012', (SELECT RouteID FROM Routes WHERE SourceAirport='ROM' AND DestAirport='ATH' LIMIT 1), 'TA-L02', '10:10', '2026-03-06', 'Arrived'),
('FL013', (SELECT RouteID FROM Routes WHERE SourceAirport='ATH' AND DestAirport='ROM' LIMIT 1), 'TA-L02', '16:30', '2026-03-06', 'Canceled');

/* ---- LARGE aircraft flights (long) ----
   long routes (>=360) -> only Large AND crew must be long-haul qualified
*/
INSERT INTO Flights VALUES
('FL020', (SELECT RouteID FROM Routes WHERE SourceAirport='TLV' AND DestAirport='NYC' LIMIT 1), 'TA-L02', '23:10', '2026-03-07', 'Active'),
('FL021', (SELECT RouteID FROM Routes WHERE SourceAirport='NYC' AND DestAirport='TLV' LIMIT 1), 'TA-L02', '10:00', '2026-03-08', 'Full'),
('FL022', (SELECT RouteID FROM Routes WHERE SourceAirport='NYC' AND DestAirport='ROM' LIMIT 1), 'TA-L01', '09:00', '2026-03-09', 'Arrived'),
('FL023', (SELECT RouteID FROM Routes WHERE SourceAirport='ROM' AND DestAirport='NYC' LIMIT 1), 'TA-L01', '18:00', '2026-03-09', 'Canceled');

-- =====================================================
-- E) ADD PRICING
--    small flights => Economy only
--    large flights => Economy + Business
-- =====================================================

/* small */
INSERT INTO FlightPricing VALUES
('FS010','Economy',125),
('FS011','Economy',125),
('FS012','Economy',145),
('FS013','Economy',145),
('FS014','Economy',110),
('FS015','Economy',110);

/* large short */
INSERT INTO FlightPricing VALUES
('FL010','Economy',160), ('FL010','Business',320),
('FL011','Economy',160), ('FL011','Business',320),
('FL012','Economy',155), ('FL012','Business',310),
('FL013','Economy',155), ('FL013','Business',310);

/* large long */
INSERT INTO FlightPricing VALUES
('FL020','Economy',950),  ('FL020','Business',1700),
('FL021','Economy',950),  ('FL021','Business',1700),
('FL022','Economy',780),  ('FL022','Business',1450),
('FL023','Economy',780),  ('FL023','Business',1450);

-- =====================================================
-- F) CREW ASSIGNMENTS (STRICT COUNTS)
--    Small flights  => 2 pilots + 3 attendants
--    Large flights  => 3 pilots + 6 attendants
--    Long flights   => use ONLY long-haul qualified crew
-- =====================================================

/* ---------- SMALL CREW TEAM S (2 pilots + 3 attendants) ----------
   Use non-long-haul pilots/attendants (allowed for short).
*/
INSERT INTO CrewPilots VALUES
('FS010',1004),('FS010',1005),
('FS011',1004),('FS011',1005),
('FS014',1004),('FS014',1005),
('FS015',1004),('FS015',1005);

INSERT INTO CrewAttendants VALUES
('FS010',2004),('FS010',2005),('FS010',2006),
('FS011',2004),('FS011',2005),('FS011',2006),
('FS014',2007),('FS014',2008),('FS014',2013),
('FS015',2007),('FS015',2008),('FS015',2013);

/* Another small crew team for TA-S02 flights */
INSERT INTO CrewPilots VALUES
('FS012',1010),('FS012',1011),
('FS013',1010),('FS013',1011);

INSERT INTO CrewAttendants VALUES
('FS012',2014),('FS012',2015),('FS012',2016),
('FS013',2014),('FS013',2015),('FS013',2016);

/* ---------- LARGE CREW TEAM L-SHORT (3 pilots + 6 attendants) ----------
   Short flights: qualification not required, but counts are required.
*/
INSERT INTO CrewPilots VALUES
('FL010',1007),('FL010',1010),('FL010',1012),
('FL011',1007),('FL011',1010),('FL011',1012),
('FL012',1008),('FL012',1011),('FL012',1012),
('FL013',1008),('FL013',1011),('FL013',1012);

INSERT INTO CrewAttendants VALUES
('FL010',2004),('FL010',2005),('FL010',2006),('FL010',2007),('FL010',2008),('FL010',2013),
('FL011',2004),('FL011',2005),('FL011',2006),('FL011',2007),('FL011',2008),('FL011',2013),
('FL012',2014),('FL012',2015),('FL012',2016),('FL012',2007),('FL012',2008),('FL012',2013),
('FL013',2014),('FL013',2015),('FL013',2016),('FL013',2007),('FL013',2008),('FL013',2013);

/* ---------- LARGE CREW TEAM L-LONG (3 pilots + 6 attendants) ----------
   Long flights: pilots must be IsLongHaulQualified=1
                attendants must be IsLongHaulQualified=1
*/
-- use long-haul pilots: 1001,1002,1003 (already qualified)
INSERT INTO CrewPilots VALUES
('FL020',1001),('FL020',1002),('FL020',1003),
('FL021',1001),('FL021',1002),('FL021',1003);

-- use 6 long-haul attendants: 2001,2002,2003 + 2009,2010,2011 (all qualified=1)
INSERT INTO CrewAttendants VALUES
('FL020',2001),('FL020',2002),('FL020',2003),('FL020',2009),('FL020',2010),('FL020',2011),
('FL021',2001),('FL021',2002),('FL021',2003),('FL021',2009),('FL021',2010),('FL021',2011);

-- another long crew set (still all qualified) for NYC<->ROM long flights
INSERT INTO CrewPilots VALUES
('FL022',1007),('FL022',1008),('FL022',1009),
('FL023',1007),('FL023',1008),('FL023',1009);

INSERT INTO CrewAttendants VALUES
('FL022',2009),('FL022',2010),('FL022',2011),('FL022',2012),('FL022',2001),('FL022',2002),
('FL023',2009),('FL023',2010),('FL023',2011),('FL023',2012),('FL023',2001),('FL023',2002);




