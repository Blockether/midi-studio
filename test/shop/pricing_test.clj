(ns shop.pricing-test
  {:clj-kondo/config '{:lint-as {lazytest.core/defdescribe clojure.core/def}}}
  (:require [lazytest.core :refer [defdescribe expect it throws?]]
            [shop.pricing :as pricing]))

(defdescribe pricing-test
  (it "adds the order lines"
      (expect (= 700 (pricing/subtotal [{:unit-cents 250 :quantity 2} {:unit-cents 200}]))))
  (it "rounds a discount down to a cent"
      (expect (= 899 (pricing/discount 999 10)))))

(defdescribe gross-test
  (it "applies each VAT rate"
      (expect (= 12300 (pricing/gross 10000 :standard)))
      (expect (= 10800 (pricing/gross 10000 :reduced)))
      (expect (= 10500 (pricing/gross 10000 :super-reduced)))
      (expect (= 10000 (pricing/gross 10000 :zero))))
  (it "rounds the gross amount half up"
      (expect (= 1 (pricing/gross 1 :standard)))
      (expect (= 8 (pricing/gross 7 :reduced)))
      (expect (= 122 (pricing/gross 99 :standard)))
      (expect (= 62 (pricing/gross 50 :standard)))
      (expect (= 11 (pricing/gross 10 :super-reduced))))
  (it "throws ex-info with the rate in the data for an unknown rate"
      (expect (throws? clojure.lang.ExceptionInfo #(pricing/gross 1000 :unknown)))
      (let [e (try (pricing/gross 1000 :unknown) (catch clojure.lang.ExceptionInfo e e))]
        (expect (= :unknown (:rate (ex-data e)))))))
