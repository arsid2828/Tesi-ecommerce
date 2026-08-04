import json
import unittest
from unittest.mock import patch

from prototype.backend.schemas import Product
from prototype.backend.services.discovery_service import discover_products


class EmptyEvidenceService:
    def evidence_for_product(self,**_kwargs):
        return []


class DiscoveryServiceTest(unittest.TestCase):
    def setUp(self):
        self.products=[
            Product(
                item_id=f"p{index}",
                title=f"Wireless Mouse Model {index}",
                category="Computer Mouse",
                description="gaming programmable" if index % 2 else "office ergonomic",
                price=10.0 + index*5,
                average_rating=4.0 + index/10,
                rating_count=100*index,
                popularity_score=1.0 - index/20,
            )
            for index in range(1,9)
        ]
        self.evidence_service=EmptyEvidenceService()

    def test_gemini_creates_groups_from_local_candidate_ids(self):
        captured={}

        def fake_gemini(prompt):
            payload=json.loads(prompt.split("Dati:\n",1)[1])
            captured["payload"]=payload
            candidate_ids=[item["item_id"] for item in payload["candidates"]]
            return json.dumps({
                "answer": "Cluster creati dinamicamente.",
                "groups": [
                    {
                        "cluster_id": "uso_quotidiano",
                        "label": "Uso quotidiano",
                        "description": "Primo cluster basato sui dati disponibili.",
                        "reason": "Usa soltanto candidati locali.",
                        "item_ids": [candidate_ids[0],candidate_ids[1],"inventato"],
                    },
                    {
                        "cluster_id": "prestazioni",
                        "label": "Prestazioni",
                        "description": "Secondo cluster basato sui dati disponibili.",
                        "reason": "Usa soltanto candidati locali.",
                        "item_ids": [candidate_ids[1],candidate_ids[2],candidate_ids[3]],
                    },
                ],
            })

        with patch("prototype.backend.services.discovery_service.call_gemini",fake_gemini):
            response=discover_products(
                self.products,
                "mouse",
                self.evidence_service,
                ai_query="separa per utilizzo",
            )

        product_ids=[product.item_id for group in response.groups for product in group.products]
        self.assertTrue(response.used_ai_support)
        self.assertEqual([group.role_id for group in response.groups],["uso_quotidiano","prestazioni"])
        self.assertNotIn("groups",captured["payload"])
        self.assertNotIn("inventato",product_ids)
        self.assertEqual(len(product_ids),len(set(product_ids)))

    def test_invalid_gemini_response_uses_local_fallback(self):
        with patch(
            "prototype.backend.services.discovery_service.call_gemini",
            return_value=json.dumps({
                "answer": "Risposta non valida",
                "groups": [{
                    "cluster_id": "inventato",
                    "label": "Inventato",
                    "description": "Contiene soltanto un ID estraneo.",
                    "item_ids": ["id_inesistente"],
                }],
            }),
        ):
            response=discover_products(self.products,"mouse",self.evidence_service)

        self.assertFalse(response.used_ai_support)
        self.assertGreaterEqual(len(response.groups),1)
        self.assertEqual(response.groups[0].role_id,"best_choice")


if __name__ == "__main__":
    unittest.main()
