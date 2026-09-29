Music creator-specialization analysis
===================================

Purpose
-------
Test the post-hoc mechanism hypothesis that month-order 伤官 may be more
prominent among explicitly creator-coded musicians than among other
Music-coded public figures.

Creator-coded roles
-------------------
- singer-songwriter
- songwriter
- composer
- record producer
- music producer
- music arranger

Sensitivity:
- creator_plus_rapper also counts rapper.

Important limitation
--------------------
"Other Music" does NOT mean true non-creator; it only means no creator
occupation was explicitly coded in Wikidata P106.

This script does NOT classify solo vs band.
Absence of band-membership metadata cannot safely be treated as evidence
of a solo career.

Run
---
python postvalidation_music_creator_specialization_1986_1992.py

Main output
-----------
postvalidation_music_creator_specialization_1986_1992\CREATOR_SPECIALIZATION_SUMMARY.txt

Also inspect
------------
creator_specialization_models.csv
creator_role_audit.csv
music_people_creator_classification_audit.csv

All results are post-validation exploratory.
