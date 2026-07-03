# eBay Browse Fixture Corpus

These fixtures are synthetic-realistic Browse API payloads authored for Phase 1. They are not copied from live eBay listings. Real recorded Browse responses can replace these files later without code changes as long as the Browse-shaped contract and stable item IDs are preserved.

Item IDs use the stable `v1|fx...|0` namespace so Phase 2 gold labels can reference them permanently.

## Trap Inventory

| Bag | Item ID | Trap | Expected label |
|---|---|---|---|
| chloe-paddington | `v1|fx-chloe-paddington-009|0` | Paddington Bear merchandise | `wrong_product_category` |
| chloe-paddington | `v1|fx-chloe-paddington-010|0` | Chloe Edith mislabeled Paddington | `wrong_model` |
| chloe-paddington | `v1|fx-chloe-paddington-014|0` | Silverado / style cross-listing | `wrong_model` |
| chloe-paddington | `v1|fx-chloe-paddington-017|0` | Inspired padlock purse | `replica_or_inspired` |
| chloe-paddington | `v1|fx-chloe-paddington-018|0` | Replacement lock/key only | `accessory_replacement_part` |
| balenciaga-city | `v1|fx-balenciaga-city-007|0` | Le City reissue separate market | `accepted_separate_market` |
| balenciaga-city | `v1|fx-balenciaga-city-008|0` | First mislabeled City | `child_mini_variant_mismatched` |
| balenciaga-city | `v1|fx-balenciaga-city-009|0` | Town mislabeled City | `wrong_model` |
| balenciaga-city | `v1|fx-balenciaga-city-010|0` | Moto style dupe | `replica_or_inspired` |
| balenciaga-city | `v1|fx-balenciaga-city-012|0` | Work mislabeled City | `wrong_model` |
| fendi-baguette | `v1|fx-fendi-baguette-007|0` | Mamma Forever separate model | `wrong_model` |
| fendi-baguette | `v1|fx-fendi-baguette-008|0` | Croissant separate model | `wrong_model` |
| fendi-baguette | `v1|fx-fendi-baguette-009|0` | Baguette charm accessory | `accessory_replacement_part` |
| fendi-baguette | `v1|fx-fendi-baguette-010|0` | Inspired FF style bag | `replica_or_inspired` |
| fendi-baguette | `v1|fx-fendi-baguette-013|0` | Peekaboo mislabel | `wrong_model` |
| dior-saddle | `v1|fx-dior-saddle-007|0` | Horse saddle tack | `wrong_product_category` |
| dior-saddle | `v1|fx-dior-saddle-008|0` | Saddle pad equestrian item | `wrong_product_category` |
| dior-saddle | `v1|fx-dior-saddle-009|0` | Gucci saddle bag | `wrong_model` |
| dior-saddle | `v1|fx-dior-saddle-010|0` | Inspired saddle-style purse | `replica_or_inspired` |
| dior-saddle | `v1|fx-dior-saddle-014|0` | Card holder | `wrong_product_category` |
| louis-vuitton-pochette-accessoires | `v1|fx-lv-pochette-007|0` | Mini Pochette separate model | `child_mini_variant_mismatched` |
| louis-vuitton-pochette-accessoires | `v1|fx-lv-pochette-008|0` | Pochette Metis separate model | `wrong_model` |
| louis-vuitton-pochette-accessoires | `v1|fx-lv-pochette-010|0` | Chain strap only | `accessory_replacement_part` |
| louis-vuitton-pochette-accessoires | `v1|fx-lv-pochette-011|0` | Insert organizer | `accessory_replacement_part` |
| louis-vuitton-pochette-accessoires | `v1|fx-lv-pochette-012|0` | LV inspired pouch | `replica_or_inspired` |
