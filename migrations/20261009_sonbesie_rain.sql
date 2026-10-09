-- Apply once to the weather database before running the TMin importer.
-- Historical observations have no rain measurement, so retain NULL defaults.
ALTER TABLE `SB_TMin`
    ADD COLUMN `Rain_1_Tot` DOUBLE NULL DEFAULT NULL,
    ADD COLUMN `Rain_1_Accumulated` DOUBLE NULL DEFAULT NULL;
