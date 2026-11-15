// Coordinates exist only in Core Location/geocoder memory, never in app output.
import AppKit
import CoreLocation
import SQLite3
import Darwin

final class CountyObserver: NSObject, CLLocationManagerDelegate {
    let manager = CLLocationManager()
    let geocoder = CLGeocoder()
    let root: URL
    var busy = false
    var requestID = 0
    var timer: Timer?
    var lockFD: Int32 = -1
    init(root: URL) {
        self.root = root
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }
    func start() {
        // Never create a replacement data directory on the internal disk.
        guard FileManager.default.fileExists(atPath: root.path) else { exit(1) }
        do { try FileManager.default.createDirectory(at: root.appendingPathComponent("station-location"), withIntermediateDirectories: true) }
        catch { exit(1) }
        lockFD = Darwin.open(root.appendingPathComponent("station-location/worker.lock").path, O_CREAT | O_RDWR, 0o600)
        guard lockFD >= 0, flock(lockFD, LOCK_EX | LOCK_NB) == 0 else { exit(0) }
        record(nil)
        manager.requestWhenInUseAuthorization()
        poll()
        timer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in self?.poll() }
    }
    func record(_ place: CLPlacemark?) {
        // No descriptions, error strings, raw placemarks, GPS, street or postal fields.
        let fields = [place?.subAdministrativeArea, place?.administrativeArea, place?.isoCountryCode]
        let known = fields.allSatisfy { v in
            guard let s = v, !s.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, s.count <= 120 else { return false }
            return !s.unicodeScalars.contains { CharacterSet.controlCharacters.contains($0) }
        }
        var db: OpaquePointer?
        let path = root.appendingPathComponent("station-location/history.sqlite").path
        guard sqlite3_open_v2(path, &db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, nil) == SQLITE_OK else { sqlite3_close(db); return }
        defer { sqlite3_close(db) }
        sqlite3_busy_timeout(db, 250)
        sqlite3_exec(db, "PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS fixes(sampled_epoch REAL PRIMARY KEY, valid_until REAL NOT NULL, status TEXT NOT NULL, county TEXT, state TEXT, country TEXT);", nil, nil, nil)
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "INSERT INTO fixes VALUES(?,?,?,?,?,?)", -1, &stmt, nil) == SQLITE_OK else { return }
        defer { sqlite3_finalize(stmt) }
        let stamp = Date().timeIntervalSince1970
        sqlite3_bind_double(stmt, 1, stamp)
        sqlite3_bind_double(stmt, 2, stamp + 180)
        let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
        sqlite3_bind_text(stmt, 3, known ? "known" : "unknown", -1, transient)
        for i in 0..<3 {
            if known { sqlite3_bind_text(stmt, Int32(i+4), fields[i]!, -1, transient) }
            else { sqlite3_bind_null(stmt, Int32(i+4)) }
        }
        sqlite3_step(stmt)
    }
    func poll() {
        guard !busy else { return }
        guard CLLocationManager.locationServicesEnabled() else { record(nil); return }
        let status = manager.authorizationStatus
        guard status == .authorizedAlways else { record(nil); return }
        busy = true
        requestID += 1
        let id = requestID
        manager.requestLocation()
        DispatchQueue.main.asyncAfter(deadline: .now()+25) { [weak self] in
            guard let self = self, self.busy, self.requestID == id else { return }
            self.requestID += 1
            self.geocoder.cancelGeocode()
            self.busy = false
            self.record(nil)
        }
    }
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if manager.authorizationStatus == .denied || manager.authorizationStatus == .restricted {
            requestID += 1; busy = false; geocoder.cancelGeocode(); record(nil)
        } else { poll() }
    }
    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        requestID += 1; busy = false; geocoder.cancelGeocode(); record(nil)
    }
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard busy, let location = locations.last else { return }
        // Stale, imprecise or moving fixes must not silently become a capture location.
        guard abs(location.timestamp.timeIntervalSinceNow) <= 60,
              location.horizontalAccuracy >= 0, location.horizontalAccuracy <= 1000,
              location.speed < 3 else { busy = false; record(nil); return }
        let id = requestID
        geocoder.reverseGeocodeLocation(location, preferredLocale: Locale(identifier: "en_US")) { [weak self] places, _ in
            guard let self = self, self.busy, self.requestID == id else { return }
            self.busy = false
            self.record(places?.first)
        }
    }
}

guard CommandLine.arguments.count == 2 else { exit(2) }
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let observer = CountyObserver(root: URL(fileURLWithPath: CommandLine.arguments[1]))
DispatchQueue.main.async { observer.start() }
app.run()
