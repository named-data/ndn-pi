# -*- Mode:python; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
#
# Copyright (C) 2014 Regents of the University of California.
# Author: Adeola Bannis <thecodemaiden@gmail.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# A copy of the GNU General Public License is in the file COPYING.


import sys

from pyndn.security.policy import ConfigPolicyManager
from pyndn import Name

from pyndn.security.security_exception import SecurityException
from pyndn.util.boost_info_parser import BoostInfoParser

import os

"""
This module implements a simple hierarchical trust model that uses certificate
data to determine whether another signature/name can be trusted.

The policy manager enforces an environment, which corresponds to the network
prefix, i.e. the root of the network namespace.
All command interests must be signed with a certificate in this environment 
to be trusted.

There is a root name and public key which must be the top authority in the environment
for the certificate to be trusted. 
"""

class IotPolicyManager(ConfigPolicyManager):
    def __init__(self, identityStorage, configFilename):
        """
        :param pyndn.IdentityStorage: A class that stores signing identities and certificates.
        :param str configFilename: A configuration file specifying validation rules and network
            name settings.
        """
        super(IotPolicyManager, self).__init__(identityStorage, configFilename)
        self.setEnvironmentPrefix(None)
        self.setTrustRootIdentity(None)

    def updateTrustRules(self, deviceIdentity):
        """
        Should be called after the device identity, trust root or environment
        prefix changes.

        Not called automatically in case they are all changing (typical for
        bootstrapping).

        Resets the validation rules if we don't have a trust root or enivronment
        """
        # TODO: use environment variable for this, fall back to default
        templateFile = '/usr/local/etc/ndn/iot/default.conf'
        newConfig = BoostInfoParser()
        newConfig.read(templateFile)
        validatorTree = newConfig["validator"][0]

        if (self._environmentPrefix is not None and 
            self._trustRootIdentity is not None):
            # don't sneak in a bad identity
            if (self._environmentPrefix is None or 
                not self._environmentPrefix.match(deviceIdentity)):
                raise SecurityException("Device identity does not belong to configured network!")
            
            environmentUri = self._environmentPrefix.toUri()
            deviceUri = deviceIdentity.toUri()
             
            for rule in validatorTree["rule"]:
                ruleId = rule["id"][0].value
                if ruleId == 'Certificate Trust':
                    #modify the 'Certificate Trust' rule
                    rule["checker/key-locator/name"][0].value = environmentUri
                elif ruleId == 'Command Interests':
                    rule["filter/name"][0].value = deviceUri
                    rule["checker/key-locator/name"][0].value = environmentUri
            
        #remove old validation rules from config
        # replace with new validator rules
        self.config._root.subtrees["validator"] = [validatorTree]
        

    def inferSigningIdentity(self, fromName):
        """
        Used to map Data or Interest names to identitites.
        :param pyndn.Name fromName: The name of a Data or Interest packet
        """
        # works if you have an IotIdentityStorage
        return self._identityStorage.inferIdentityForName(fromName)

    def setTrustRootIdentity(self, identityName):
        """
        : param pyndn.Name identityName: The new identity to trust as the controller.
        """
        self._trustRootIdentity = Name(identityName)

    def getTrustRootIdentity(self):
        """
        : return pyndn.Name: The trusted controller's network name.
        """
        return self._trustRootIdentity

    def setEnvironmentPrefix(self, name):
        """
        : param pyndn.Name name: The new root of the network namespace (network prefix)
        """
        self._environmentPrefix = Name(name)

    def getEnvironmentPrefix(self):
        """
        :return pyndn.Name: The root of the network namespace
        """
        return self._environmentPrefix

    def hasRootCertificate(self):
        """
        :return boolean: Whether we've downloaded the controller's network certificate
        """
        try:
            rootCertName = self._identityStorage.getDefaultCertificateNameForIdentity(
                    self._trustRootIdentity)
        except SecurityException:
            return False

        try:
            rootCert = self._identityStorage.getCertificate(rootCertName)
            if rootCert is not None:
                return True
        finally:
            return False

    def hasRootSignedCertificate(self):
       """
       :return boolean: Whether we've received a network certificate from our controller
       """
       try:
           myCertName = self._identityStorage.getDefaultCertificateNameForIdentity(
                       self._identityStorage.getDefaultIdentity())
           myCert = self._identityStorage.getCertificate(myCertName)
           if self._trustRootIdentity.match(
                   myCert.getSignature().getKeyLocator().getKeyName()):
               return True
       except SecurityException:
           pass
       
       return False