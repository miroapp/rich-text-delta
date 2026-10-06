import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    kotlin("jvm") version "2.4.10"
    kotlin("plugin.serialization") version "2.4.10"
    id("org.jlleitschuh.gradle.ktlint") version "14.2.0"
    `java-library`
    `maven-publish`
}

repositories {
    mavenCentral()
}

dependencies {
    api("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0")
    implementation("org.bitbucket.cowwoc:diff-match-patch:1.2")

    testImplementation(platform("org.junit:junit-bom:5.14.0"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    testImplementation("org.snakeyaml:snakeyaml-engine:2.9")
}

java {
    withSourcesJar()
}

tasks.withType<JavaCompile>().configureEach {
    options.release = 17
}

kotlin {
    explicitApi()
    compilerOptions {
        jvmTarget = JvmTarget.JVM_17
    }
}

publishing {
    publications {
        create<MavenPublication>("maven") {
            from(components["java"])
            pom {
                name = "rich-text-delta"
                description = "Kotlin/JVM implementation of Rich Text Delta, a fork of quill-delta with nested attribute maps"
                licenses {
                    license {
                        name = "BSD-3-Clause"
                        url = "https://opensource.org/license/bsd-3-clause"
                    }
                }
            }
        }
    }
}

ktlint {
    version = "1.8.0"
}

val corpusDir = layout.projectDirectory.dir("../../declarative-test-corpus")

tasks.test {
    useJUnitPlatform()
    inputs.dir(corpusDir).withPropertyName("corpus").withPathSensitivity(PathSensitivity.RELATIVE)
    systemProperty("corpus.root", corpusDir.asFile.absolutePath)
    testLogging {
        events("failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
