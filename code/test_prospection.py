"""Régressions ciblées sur les exclusions et le rattachement RCB."""

import json
import unittest

from prospection import Criteria, analyse


def parcel():
    return {
        "egrid": "CH_TEST", "numero_parcelle": "846",
        "surface_geometrique_m2": "1500", "emprise_batie_m2": "150",
        "taux_emprise_geometrique": "0.1", "batiments_nombre": "1",
        "zone_dominante": "Zone de villas", "zone_dominante_part_surface": "1",
        "notes_batiment_existante_json": "[]", "notes_batiment_provisoire_json": "[]",
        "notes_site_existante_json": "[]", "notes_site_provisoire_json": "[]",
        "sigip_rcb_bat_json": json.dumps([{
            "egid": 123, "parcelle": "846", "statut": "existant", "nbre_logements": 1,
        }]),
    }


class ExclusionRegressionTests(unittest.TestCase):
    def test_provisional_three_excludes_entire_parcel(self):
        row = parcel()
        row["notes_batiment_provisoire_json"] = '["3 provisoire"]'
        self.assertEqual(analyse(row, Criteria())["statut"], "exclue_patrimoine")

    def test_site_two_excludes_even_when_building_is_four(self):
        row = parcel()
        row["notes_batiment_existante_json"] = "[4]"
        row["notes_site_provisoire_json"] = "[2]"
        self.assertEqual(analyse(row, Criteria())["statut"], "exclue_patrimoine")

    def test_provisional_four_does_not_override_existing_three(self):
        row = parcel()
        row["notes_batiment_existante_json"] = "[3, 3]"
        row["notes_batiment_provisoire_json"] = "[4]"
        self.assertEqual(analyse(row, Criteria())["statut"], "exclue_patrimoine")

    def test_false_csv_flag_does_not_exclude(self):
        row = parcel()
        row["presence_note_1_3_batiment_existante"] = "False"
        self.assertEqual(analyse(row, Criteria())["statut"], "candidate_a_approfondir")

    def test_invalid_or_zero_note_requires_review(self):
        for value in ("not-json", "[0]", "[null]"):
            with self.subTest(value=value):
                row = parcel()
                row["notes_batiment_existante_json"] = value
                self.assertEqual(analyse(row, Criteria())["statut"], "a_verifier_donnees")

    def test_neighbor_building_does_not_add_dwellings(self):
        row = parcel()
        records = json.loads(row["sigip_rcb_bat_json"])
        records.append({"egid": 124, "parcelle": "847", "statut": "existant", "nbre_logements": 9})
        row["sigip_rcb_bat_json"] = json.dumps(records)
        result = analyse(row, Criteria())
        self.assertEqual(result["statut"], "a_verifier_donnees")
        self.assertEqual(result["logements_rattachement_declare"], 1)

    def test_missing_dwellings_are_not_zero(self):
        row = parcel()
        row["sigip_rcb_bat_json"] = '[{"egid":123,"parcelle":"846","statut":"existant","nbre_logements":null}]'
        result = analyse(row, Criteria())
        self.assertIsNone(result["logements_rattachement_declare"])
        self.assertEqual(result["statut"], "a_verifier_donnees")

    def test_cartographic_note_is_checked_even_if_detailed_note_is_missing(self):
        row = parcel()
        row["sigip_rec_arch_s_json"] = '[{"num_eca":"123","note_detail":null,"note_carto":2}]'
        self.assertEqual(analyse(row, Criteria())["statut"], "exclue_patrimoine")


if __name__ == "__main__":
    unittest.main()
