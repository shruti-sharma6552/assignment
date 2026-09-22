-- CinePrice — MySQL schema and demo data.
-- Run with:  mysql -u root -p < database.sql
--
-- The Flask app also creates these tables automatically on first run, so this
-- file is an alternative to `python app.py`, not a prerequisite.

DROP DATABASE IF EXISTS cineprice;
CREATE DATABASE cineprice CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cineprice;

-- ---------------------------------------------------------------- tables --
CREATE TABLE memberships (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  name                VARCHAR(90)   NOT NULL UNIQUE,
  discount_percentage DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
  discount_cap        DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  active              BOOLEAN       NOT NULL DEFAULT TRUE,
  INDEX idx_membership_active (active)
) ENGINE=InnoDB;

CREATE TABLE users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(120) NOT NULL,
  email         VARCHAR(120) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(20)  NOT NULL DEFAULT 'CUSTOMER',
  membership_id INT NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_role (role),
  CONSTRAINT fk_user_membership FOREIGN KEY (membership_id)
    REFERENCES memberships(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE cinemas (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(150) NOT NULL,
  location   VARCHAR(150) NOT NULL,
  address    VARCHAR(255) NULL,
  city       VARCHAR(100) NOT NULL,
  screen_direction VARCHAR(20) NOT NULL DEFAULT 'top',
  normal_seats     INT NOT NULL DEFAULT 0,
  normal_row_length INT NOT NULL DEFAULT 15,
  silver_seats     INT NOT NULL DEFAULT 0,
  silver_row_length INT NOT NULL DEFAULT 15,
  gold_seats       INT NOT NULL DEFAULT 0,
  gold_row_length  INT NOT NULL DEFAULT 15,
  diamond_seats    INT NOT NULL DEFAULT 0,
  diamond_row_length INT NOT NULL DEFAULT 15,
  platinum_seats   INT NOT NULL DEFAULT 0,
  platinum_row_length INT NOT NULL DEFAULT 15,
  recliner_seats   INT NOT NULL DEFAULT 0,
  recliner_row_length INT NOT NULL DEFAULT 15,
  status     VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_cinema_city (city),
  INDEX idx_cinema_status (status)
) ENGINE=InnoDB;

CREATE TABLE movies (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(180) NOT NULL,
  description TEXT NULL,
  duration    INT          NOT NULL DEFAULT 120,
  language    VARCHAR(60)  NOT NULL DEFAULT 'English',
  genre       VARCHAR(90)  NULL,
  certificate VARCHAR(10)  NULL,
  poster      VARCHAR(255) NULL,
  status      VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_movie_title (title),
  INDEX idx_movie_status (status)
) ENGINE=InnoDB;

CREATE TABLE shows (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  movie_id   INT  NOT NULL,
  cinema_id  INT  NOT NULL,
  show_date  DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time   TIME NULL,
  status     VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
  INDEX idx_show_date (show_date),
  INDEX idx_show_status (status),
  CONSTRAINT fk_show_movie  FOREIGN KEY (movie_id)  REFERENCES movies(id)  ON DELETE CASCADE,
  CONSTRAINT fk_show_cinema FOREIGN KEY (cinema_id) REFERENCES cinemas(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE seat_tiers (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  show_id         INT          NOT NULL,
  name            VARCHAR(60)  NOT NULL,
  price           DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  total_seats     INT          NOT NULL DEFAULT 0,
  available_seats INT          NOT NULL DEFAULT 0,
  status          VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
  UNIQUE KEY uq_seat_tier_show_name (show_id, name),
  INDEX idx_tier_status (status),
  CONSTRAINT fk_tier_show FOREIGN KEY (show_id) REFERENCES shows(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE discounts (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(120)  NOT NULL,
  amount     DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  start_date DATE          NOT NULL,
  end_date   DATE          NOT NULL,
  active     BOOLEAN       NOT NULL DEFAULT TRUE,
  INDEX idx_discount_active (active)
) ENGINE=InnoDB;

CREATE TABLE pricing_config (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  convenience_fee DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  gst_rate        DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
  surge_threshold_percent DECIMAL(5,2) NOT NULL DEFAULT 80.00,
  surge_percentage DECIMAL(5,2) NOT NULL DEFAULT 20.00,
  updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE bookings (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  booking_id   VARCHAR(40)   NOT NULL UNIQUE,
  user_id      INT           NOT NULL,
  show_id      INT           NOT NULL,
  total_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  status       VARCHAR(20)   NOT NULL DEFAULT 'CONFIRMED',
  created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_booking_created (created_at),
  INDEX idx_booking_status (status),
  CONSTRAINT fk_booking_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_booking_show FOREIGN KEY (show_id) REFERENCES shows(id)
) ENGINE=InnoDB;

-- Every pricing value is frozen here so old invoices never change.
CREATE TABLE booking_items (
  id                      INT AUTO_INCREMENT PRIMARY KEY,
  booking_id              INT           NOT NULL,
  seat_tier_id            INT           NULL,
  seat_tier               VARCHAR(60)   NOT NULL,
  ticket_price_at_booking DECIMAL(10,2) NOT NULL,
  quantity                INT           NOT NULL,
  booked_seats            TEXT          NULL,
  base_amount             DECIMAL(12,2) NOT NULL,
  festival_discount       DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  member_discount         DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  discounted_amount       DECIMAL(12,2) NOT NULL,
  convenience_fee         DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  taxable_amount          DECIMAL(12,2) NOT NULL,
  gst_rate                DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
  gst_amount              DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  final_amount            DECIMAL(12,2) NOT NULL,
  membership_name         VARCHAR(90)   NULL,
  festival_name           VARCHAR(120)  NULL,
  CONSTRAINT fk_item_booking FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
  CONSTRAINT fk_item_tier    FOREIGN KEY (seat_tier_id) REFERENCES seat_tiers(id)
) ENGINE=InnoDB;

CREATE TABLE invoices (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  invoice_number VARCHAR(40)   NOT NULL UNIQUE,
  booking_id     INT           NOT NULL UNIQUE,
  total_amount   DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  gst_amount     DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  issued_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_invoice_booking FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------- demo data ----
INSERT INTO memberships (name, discount_percentage, discount_cap, active) VALUES
  ('Silver Member',   5.00,  30.00, TRUE),
  ('Gold Member',    10.00,  50.00, TRUE),
  ('Premium Member', 15.00, 100.00, TRUE);

-- Demo credentials for localhost only: admin123 / customer123.
INSERT INTO users (name, email, password_hash, role, membership_id) VALUES
  ('Cinema Admin', 'admin@cineprice.com',    'scrypt:32768:8:1$RNiWh4MejXP2qtrH$0c679127fec732edf51aa5cb76e59a9371ae34b005041d049b4c3152290e11bfbd5e3d2044ccc7cd39f474a37e60e0358ec1819a550c3041186a01bb174b1cc8', 'ADMIN',    NULL),
  ('Shruti',       'customer@cineprice.com', 'scrypt:32768:8:1$F88C2dZzp0QvGzLa$b638de8916517f32967d68ee0b377a6a8f57a657e273566f682c46306bb81f8074f99a55693931d68f69a6149f532693411d6c7e243e45b80fc8eefaa6fa60a3', 'CUSTOMER', 2);

INSERT INTO cinemas (name, location, address, city, status) VALUES
  ('Cineplex Jaipur', 'MI Road',      '12 MI Road, Jaipur',              'Jaipur', 'ACTIVE'),
  ('CineMax Central', 'Central Mall', 'Central Mall, Tonk Road, Jaipur', 'Jaipur', 'ACTIVE');

INSERT INTO movies (title, description, duration, language, genre, certificate, status) VALUES
  ('Avengers',     'Earth''s mightiest heroes reunite for one last stand.',      143, 'English', 'Action', 'UA', 'ACTIVE'),
  ('Inception',    'A thief who steals secrets from dreams takes a final job.',  148, 'English', 'Sci-Fi', 'UA', 'ACTIVE'),
  ('Interstellar', 'A crew travels through a wormhole to find a new home.',      169, 'English', 'Sci-Fi', 'U',  'ACTIVE');

INSERT INTO shows (movie_id, cinema_id, show_date, start_time, end_time, status) VALUES
  (1, 1, '2026-09-20', '19:30:00', '21:53:00', 'ACTIVE'),
  (1, 2, '2026-09-20', '16:00:00', '18:23:00', 'ACTIVE'),
  (2, 1, '2026-09-21', '18:00:00', '20:28:00', 'ACTIVE'),
  (3, 2, '2026-09-21', '20:15:00', '23:04:00', 'ACTIVE');

-- Show 1 has a sold-out Recliner tier to demonstrate the SOLD OUT state.
INSERT INTO seat_tiers (show_id, name, price, total_seats, available_seats, status) VALUES
  (1, 'Silver',   150.00, 100, 45,  'ACTIVE'),
  (1, 'Gold',     250.00,  80, 20,  'ACTIVE'),
  (1, 'Recliner', 450.00,  30,  0,  'ACTIVE'),
  (2, 'Silver',   150.00, 100, 100, 'ACTIVE'),
  (2, 'Gold',     250.00,  80, 80,  'ACTIVE'),
  (2, 'Recliner', 450.00,  30, 30,  'ACTIVE'),
  (3, 'Silver',   150.00, 100, 100, 'ACTIVE'),
  (3, 'Gold',     250.00,  80, 80,  'ACTIVE'),
  (3, 'Recliner', 450.00,  30, 30,  'ACTIVE'),
  (4, 'Silver',   150.00, 100, 100, 'ACTIVE'),
  (4, 'Gold',     250.00,  80, 80,  'ACTIVE'),
  (4, 'Recliner', 450.00,  30, 30,  'ACTIVE');

INSERT INTO discounts (name, amount, start_date, end_date, active) VALUES
  ('Festival Offer', 100.00, '2026-08-17', '2027-03-15', TRUE);

INSERT INTO pricing_config (convenience_fee, gst_rate) VALUES (20.00, 18.00);
