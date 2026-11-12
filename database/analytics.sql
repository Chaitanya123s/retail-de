
-- 1. Total sales summary
SELECT
    COUNT(*) AS total_transactions,
    SUM(quantity) AS units_sold,
    ROUND(SUM(sales_amount), 2) AS total_revenue
FROM fact_sales;


-- 2. Revenue by product category
SELECT
    p.category,
    COUNT(*) AS transaction_lines,
    SUM(f.quantity) AS units_sold,
    ROUND(SUM(f.sales_amount), 2) AS revenue
FROM fact_sales f
JOIN dim_product p
    ON f.product_key = p.product_key
GROUP BY p.category
ORDER BY revenue DESC;


-- 3. Monthly revenue by category
SELECT
    d.year,
    d.month,
    p.category,
    ROUND(SUM(f.sales_amount), 2) AS revenue
FROM fact_sales f
JOIN dim_date d
    ON f.date_key = d.date_key
JOIN dim_product p
    ON f.product_key = p.product_key
GROUP BY d.year, d.month, p.category
ORDER BY d.year, d.month, revenue DESC;


-- 4. Top 10 products by revenue
SELECT
    p.product_id,
    p.product_name,
    SUM(f.quantity) AS units_sold,
    ROUND(SUM(f.sales_amount), 2) AS revenue
FROM fact_sales f
JOIN dim_product p
    ON f.product_key = p.product_key
GROUP BY p.product_id, p.product_name
ORDER BY revenue DESC
LIMIT 10;


-- 5. Sales by store region
SELECT
    s.region,
    COUNT(*) AS transaction_lines,
    ROUND(SUM(f.sales_amount), 2) AS revenue
FROM fact_sales f
JOIN dim_store s
    ON f.store_key = s.store_key
GROUP BY s.region
ORDER BY revenue DESC;


-- 6. Top 10 customers by revenue
SELECT
    c.customer_id,
    c.customer_name,
    ROUND(SUM(f.sales_amount), 2) AS revenue
FROM fact_sales f
JOIN dim_customer c
    ON f.customer_key = c.customer_key
GROUP BY c.customer_id, c.customer_name
ORDER BY revenue DESC
LIMIT 10;


-- 7. Rejection reasons
SELECT
    reject_reason,
    COUNT(*) AS rejected_records
FROM rejected_records
GROUP BY reject_reason
ORDER BY rejected_records DESC;


-- 8. Pipeline execution history
SELECT
    run_id,
    status,
    rows_read,
    rows_loaded,
    rows_rejected,
    rows_skipped,
    started_at,
    ended_at
FROM etl_runs
ORDER BY started_at DESC;
