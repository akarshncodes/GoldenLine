"""FR-21 Medical Resource/Inventory."""


def test_create_and_list_item(client):
    res = client.post(
        "/hospitals/HOSP-001/inventory",
        json={"item_name": "Paracetamol 500mg", "category": "medicine", "unit": "strip", "quantity_on_hand": 50},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["quantity_on_hand"] == 50
    assert body["is_low_stock"] is False

    listed = client.get("/hospitals/HOSP-001/inventory").json()
    assert any(i["item_id"] == body["item_id"] for i in listed)


def test_unknown_hospital_404s(client):
    res = client.post(
        "/hospitals/HOSP-999/inventory",
        json={"item_name": "X", "category": "medicine", "unit": "unit"},
    )
    assert res.status_code == 404


def test_receptionist_scoped_to_own_hospital(client_factory):
    recep1 = client_factory("recep-hosp-001")
    recep4 = client_factory("recep-hosp-004")

    ok = recep1.post(
        "/hospitals/HOSP-001/inventory",
        json={"item_name": "Gloves", "category": "ppe", "unit": "box"},
    )
    assert ok.status_code == 200

    forbidden = recep4.post(
        "/hospitals/HOSP-001/inventory", json={"item_name": "X", "category": "ppe", "unit": "box"}
    )
    assert forbidden.status_code == 403
    assert recep4.get("/hospitals/HOSP-001/inventory").status_code == 403


def test_adjust_quantity_and_movement_audit(client):
    item = client.post(
        "/hospitals/HOSP-001/inventory",
        json={"item_name": "Syringes", "category": "consumable", "unit": "box", "quantity_on_hand": 10},
    ).json()

    res = client.post(f"/inventory/{item['item_id']}/adjust", json={"delta": 20, "reason": "restock"})
    assert res.status_code == 200
    assert res.json()["quantity_on_hand"] == 30

    res2 = client.post(f"/inventory/{item['item_id']}/adjust", json={"delta": -5, "reason": "consumed"})
    assert res2.status_code == 200
    assert res2.json()["quantity_on_hand"] == 25

    movements = client.get(f"/inventory/{item['item_id']}/movements").json()
    assert len(movements) == 2
    assert movements[0]["delta"] == -5  # newest first
    assert movements[0]["reason"] == "consumed"
    assert movements[1]["delta"] == 20
    assert movements[1]["reason"] == "restock"


def test_adjust_floors_at_zero(client):
    item = client.post(
        "/hospitals/HOSP-001/inventory",
        json={"item_name": "Bandages", "category": "consumable", "unit": "roll", "quantity_on_hand": 3},
    ).json()

    res = client.post(f"/inventory/{item['item_id']}/adjust", json={"delta": -10, "reason": "consumed"})
    assert res.status_code == 200
    assert res.json()["quantity_on_hand"] == 0

    movements = client.get(f"/inventory/{item['item_id']}/movements").json()
    assert movements[0]["delta"] == -3  # actual delta applied, not the requested -10


def test_low_stock_flag(client):
    item = client.post(
        "/hospitals/HOSP-001/inventory",
        json={
            "item_name": "O2 Cylinders", "category": "equipment", "unit": "unit",
            "quantity_on_hand": 5, "low_stock_threshold": 3,
        },
    ).json()
    assert item["is_low_stock"] is False

    client.post(f"/inventory/{item['item_id']}/adjust", json={"delta": -3, "reason": "consumed"})
    updated = client.get("/hospitals/HOSP-001/inventory").json()
    found = next(i for i in updated if i["item_id"] == item["item_id"])
    assert found["quantity_on_hand"] == 2
    assert found["is_low_stock"] is True


def test_import_reason_value_round_trips_correctly(client):
    """Regression guard: MovementReason.import_'s VALUE is 'import', not the
    Python identifier 'import_' — confirms values_callable is wired correctly."""
    item = client.post(
        "/hospitals/HOSP-001/inventory",
        json={"item_name": "X", "category": "other", "unit": "unit", "quantity_on_hand": 1},
    ).json()
    res = client.post(f"/inventory/{item['item_id']}/adjust", json={"delta": 5, "reason": "import"})
    assert res.status_code == 200
    movements = client.get(f"/inventory/{item['item_id']}/movements").json()
    assert movements[0]["reason"] == "import"


def test_unknown_item_404s(client):
    assert client.post("/inventory/does-not-exist/adjust", json={"delta": 1, "reason": "restock"}).status_code == 404
    assert client.get("/inventory/does-not-exist/movements").status_code == 404


def test_admin_only_unscoped_inventory_list(client, client_factory):
    client.post("/hospitals/HOSP-001/inventory", json={"item_name": "A", "category": "medicine", "unit": "unit"})
    client.post("/hospitals/HOSP-004/inventory", json={"item_name": "B", "category": "medicine", "unit": "unit"})

    res = client.get("/inventory")
    assert res.status_code == 200
    hospital_ids = {i["hospital_id"] for i in res.json()}
    assert {"HOSP-001", "HOSP-004"}.issubset(hospital_ids)

    recep = client_factory("recep-hosp-001")
    assert recep.get("/inventory").status_code == 403
