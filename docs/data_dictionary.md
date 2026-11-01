# Pagila Data Dictionary & Reference Queries

## 1. Dataset Metadata

- **Dataset:** Pagila (DVD-rental business database)
- **Source:** [https://github.com/devrimgunduz/pagila](https://github.com/devrimgunduz/pagila)
- **Version:** v4.x (PostgreSQL 18 compatible)
- **License:** PostgreSQL License (Permissive open source)
- **Loaded into:** `pagila` database on PostgreSQL 18 (Docker)

---

## 2. Core Tables Overview

| Table | Description |
|---|---|
| `customer` | Stores customer profile information including names, emails, active status, and address foreign keys. |
| `film` | Contains movie catalog details including title, release year, rental duration, rental rate, length, and MPAA rating. |
| `actor` | Details of actors appearing in films (first name, last name). |
| `film_actor` | Many-to-many junction table mapping films to actors. |
| `category` | Movie genre categories (e.g., Action, Comedy, Drama, Sci-Fi). |
| `film_category` | Many-to-many junction table mapping films to categories. |
| `inventory` | Physical copies of DVD inventory available at specific store locations. |
| `rental` | Records of individual rental transactions tracking checkout and return timestamps. |
| `payment` | Financial transaction records storing dollar amounts, customer IDs, staff IDs, and payment dates (partitioned by month). |
| `store` | Physical store locations and manager staff references. |
| `staff` | Employee profiles and credentials tied to specific stores. |
| `address` | Street addresses and postal codes for customers, staff, and stores. |
| `city` | City names referenced by addresses. |
| `country` | Country names referenced by cities. |

---

## 3. Key Joins & Relationships

- **`customer` → `rental` (`customer_id`):** One customer can have multiple rental transactions over time.
- **`rental` → `inventory` (`inventory_id`):** Each rental transaction corresponds to one physical DVD disc in inventory.
- **`inventory` → `film` (`film_id`):** Multiple inventory items correspond to copies of the same film.
- **`rental` → `payment` (`rental_id`):** Payments are linked directly to rentals.
- **`film` ↔ `category` (via `film_category`):** Many-to-many mapping of films to genre categories.
- **`film` ↔ `actor` (via `film_actor`):** Many-to-many mapping of films to participating cast members.
- **`customer` / `store` → `address` → `city` → `country`:** Geographic normalized hierarchy.

---

## 4. 10 Hand-Computed Reference Business Questions

### Q1: How many active customers are there?
- **SQL:**
  ```sql
  SELECT count(*) FROM customer WHERE active = 1;
  ```
- **Answer:** *966*

### Q2: How many films are in each rating category?
- **SQL:**
  ```sql
  SELECT rating, count(*) FROM film GROUP BY rating ORDER BY rating;
  ```
- **Answer:*: G: 198, PG: 194, PG-13: 223,R:195, NC-17:210*

### Q3: Which store has the most rentals?
- **SQL:**
  ```sql
  SELECT i.store_id, count(r.rental_id) AS total_rentals
  FROM rental r
  JOIN inventory i ON r.inventory_id = i.inventory_id
  GROUP BY i.store_id
  ORDER BY total_rentals DESC;
  ```
- **Answer:** *2: 26044,1: 25761*

### Q4: What is the total revenue per store?
- **SQL:**
  ```sql
  SELECT s.store_id, round(sum(p.amount), 2) AS total_revenue
  FROM payment p
  JOIN staff s ON p.staff_id = s.staff_id
  GROUP BY s.store_id
  ORDER BY s.store_id;
  ```
- **Answer:** *25: 85259.82,33: 85702.57*

### Q5: Which film category generates the most rental revenue?
- **SQL:**
  ```sql
  SELECT c.name, round(sum(p.amount), 2) AS total_revenue
  FROM payment p
  JOIN rental r ON p.rental_id = r.rental_id
  JOIN inventory i ON r.inventory_id = i.inventory_id
  JOIN film_category fc ON i.film_id = fc.film_id
  JOIN category c ON fc.category_id = c.category_id
  GROUP BY c.name
  ORDER BY total_revenue DESC
  LIMIT 1;
  ```
- **Answer:** *Action: 26505.44*

### Q6: Who are the top 5 customers by total payments?
- **SQL:**
  ```sql
  SELECT c.customer_id, c.first_name, c.last_name, round(sum(p.amount), 2) AS total_paid
  FROM customer c
  JOIN payment p ON c.customer_id = p.customer_id
  GROUP BY c.customer_id, c.first_name, c.last_name
  ORDER BY total_paid DESC
  LIMIT 5;
  ```
- **Answer:** * 526	"KARL"	    "SEAL"	    358.12
                468	"TIM"	    "CARY"	    344.06
                380	"RUSSELL"	"BRINSON"	324.04
                368	"HARRY"	    "ARCE"	    323.17
                295	"DAISY"	    "BATES"	    322.12*

### Q7: What is the average rental duration (in days) per film rating?
- **SQL:**
  ```sql
  SELECT rating, round(avg(rental_duration), 2) AS avg_duration
  FROM film
  GROUP BY rating
  ORDER BY rating;
  ```
- **Answer:** *G: 4.84,PG: 5.08,PG-13: 5.05,R: 4.77,NC-17: 5.14*

### Q8: How many films have never been rented?
- **SQL:**
  ```sql
  SELECT count(*) 
  FROM film f
  LEFT JOIN inventory i ON f.film_id = i.film_id
  LEFT JOIN rental r ON i.inventory_id = r.inventory_id
  WHERE r.rental_id IS NULL;
  ```
- **Answer:** *42*

### Q9: Which actor appears in the most films?
- **SQL:**
  ```sql
  SELECT a.actor_id, a.first_name, a.last_name, count(fa.film_id) AS film_count
  FROM actor a
  JOIN film_actor fa ON a.actor_id = fa.actor_id
  GROUP BY a.actor_id, a.first_name, a.last_name
  ORDER BY film_count DESC
  LIMIT 1;
  ```
- **Answer:** *GINA DEGENERES: 42*

### Q10: What is the monthly payment total for 2022?
- **SQL:**
  ```sql
  SELECT to_char(payment_date, 'YYYY-MM') AS month, round(sum(amount), 2) AS total_amount
  FROM payment
  WHERE payment_date >= '2022-01-01' AND payment_date < '2023-01-01'
  GROUP BY to_char(payment_date, 'YYYY-MM')
  ORDER BY month;
  ```
- **Answer:** * "2022-01"	3094.78
                "2022-02"	10164.97
                "2022-03"	11413.86
                "2022-04"	10759.52
                "2022-05"	11347.28
                "2022-06"	10923.45
                "2022-07"	9712.65
                "2022-08"	278.17
                "2022-09"	2128.82
                "2022-10"	1979.06
                "2022-11"	2214.64
                "2022-12"	2350.10*