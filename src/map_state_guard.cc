#include "map_state_guard.h"

#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "db.h"
#include "platform_compat.h"
#include "settings.h"

namespace fallout {

static bool gMapStateGuardEnabled = false;

// File name (upper case, "ARVILLAG.SAV") -> the bytes the server last wrote there.
static std::map<std::string, std::vector<unsigned char>> gMapStateKept;

static std::string mapStateKey(const char* fileName)
{
    std::string key(fileName != nullptr ? fileName : "");
    for (char& ch : key) {
        if (ch >= 'a' && ch <= 'z') {
            ch = static_cast<char>(ch - 'a' + 'A');
        }
    }
    return key;
}

static void mapStatePath(const std::string& key, char* path, size_t size)
{
    snprintf(path, size, "%s\\%s\\%s", settings.system.master_patches_path.c_str(), "MAPS", key.c_str());
}

static bool mapStateRead(const char* path, std::vector<unsigned char>& bytes)
{
    FILE* stream = compat_fopen(path, "rb");
    if (stream == nullptr) {
        return false;
    }

    bytes.clear();
    unsigned char buffer[32768];
    size_t count;
    while ((count = fread(buffer, 1, sizeof(buffer), stream)) > 0) {
        bytes.insert(bytes.end(), buffer, buffer + count);
    }

    bool ok = ferror(stream) == 0;
    fclose(stream);
    return ok;
}

static bool mapStateWrite(const char* path, const std::vector<unsigned char>& bytes)
{
    FILE* stream = compat_fopen(path, "wb");
    if (stream == nullptr) {
        return false;
    }

    bool ok = bytes.empty() || fwrite(bytes.data(), 1, bytes.size(), stream) == bytes.size();
    if (fclose(stream) != 0) {
        ok = false;
    }
    return ok;
}

void mapStateGuardEnable()
{
    gMapStateGuardEnabled = true;
}

bool mapStateGuardCapture(const char* fileName)
{
    if (!gMapStateGuardEnabled || fileName == nullptr || fileName[0] == '\0') {
        return true;
    }

    std::string key = mapStateKey(fileName);
    char path[COMPAT_MAX_PATH];
    mapStatePath(key, path, sizeof(path));

    std::vector<unsigned char> bytes;
    if (!mapStateRead(path, bytes)) {
        return false;
    }

    gMapStateKept[key].swap(bytes);
    return true;
}

void mapStateGuardCaptureAll()
{
    if (!gMapStateGuardEnabled) {
        return;
    }

    char pattern[COMPAT_MAX_PATH];
    snprintf(pattern, sizeof(pattern), "%s\\*.%s", "MAPS", "SAV");

    char** fileNames;
    int count = fileNameListInit(pattern, &fileNames, 0, 0);
    if (count == -1) {
        return;
    }

    for (int index = 0; index < count; index++) {
        mapStateGuardCapture(fileNames[index]);
    }

    fileNameListFree(&fileNames, 0);
}

void mapStateGuardForget(const char* fileName)
{
    if (!gMapStateGuardEnabled || fileName == nullptr) {
        return;
    }

    gMapStateKept.erase(mapStateKey(fileName));
}

void mapStateGuardForgetAll()
{
    gMapStateKept.clear();
}

int mapStateGuardRestoreMissing()
{
    if (!gMapStateGuardEnabled || gMapStateKept.empty()) {
        return 0;
    }

    int restored = 0;
    int failed = 0;
    std::string names;

    for (const auto& entry : gMapStateKept) {
        char path[COMPAT_MAX_PATH];
        mapStatePath(entry.first, path, sizeof(path));

        FILE* present = compat_fopen(path, "rb");
        if (present != nullptr) {
            fclose(present);
            continue;
        }

        if (restored == 0 && failed == 0) {
            // The folder itself may be gone too; _map_save makes it the same way.
            char folder[COMPAT_MAX_PATH];
            snprintf(folder, sizeof(folder), "%s", settings.system.master_patches_path.c_str());
            compat_mkdir(folder);
            snprintf(folder, sizeof(folder), "%s\\%s", settings.system.master_patches_path.c_str(), "MAPS");
            compat_mkdir(folder);
        }

        if (mapStateWrite(path, entry.second)) {
            restored++;
        } else {
            failed++;
        }

        if (names.size() < 160) {
            if (!names.empty()) {
                names += ", ";
            }
            names += entry.first;
        }
    }

    if (restored > 0 || failed > 0) {
        fprintf(stderr, "f2_server: %d map state file(s) of this world were ERASED from %s\\MAPS by another"
                        " program (a Fallout 2 game or an older co-op client started in this folder);"
                        " %d put back, %d could not be written: %s\n",
            restored + failed, settings.system.master_patches_path.c_str(), restored, failed,
            names.c_str());
    }

    return restored;
}

} // namespace fallout
