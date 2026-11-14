(ns shop.pricing
  "Price rules of the shop, in cents.")

(defn line-total
  "Return the total of one order line."
  [{:keys [unit-cents quantity] :or {quantity 1}}]
  (* (long unit-cents) (long quantity)))

(defn subtotal
  "Return the sum of the order lines."
  [lines]
  (reduce + 0 (map line-total lines)))

(defn discount
  "Return the price after a discount of `percent`, rounded down to a cent."
  [^long cents ^long percent]
  {:pre [(<= 0 percent 100)]}
  (quot (* cents (- 100 percent)) 100))

(def vat-rates
  "VAT rates in percent, by rate name."
  {:standard 23
   :reduced 8
   :super-reduced 5
   :zero 0})

(defn gross
  "Return the gross amount in grosze for the net amount `net-grosze` at the VAT
  rate `rate-name`, rounded half up. Throw `ex-info` with the rate in the data
  for a rate name that `vat-rates` does not know."
  [^long net-grosze rate-name]
  (if-let [percent (get vat-rates rate-name)]
    (let [numerator (* net-grosze (+ 100 (long percent)))
          whole (quot numerator 100)
          remainder (long (mod numerator 100))]
      (if (>= (* 2 remainder) 100)
        (inc whole)
        whole))
    (throw (ex-info (str "Unknown VAT rate: " rate-name) {:rate rate-name}))))
